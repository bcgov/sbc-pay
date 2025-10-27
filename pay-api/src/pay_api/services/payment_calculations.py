"""Service Helper to payment statement related calculations."""

# Copyright © 2025 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from collections import defaultdict
from dataclasses import dataclass, field, fields
from datetime import datetime
from decimal import Decimal

import cattrs
import humps
from sqlalchemy import and_, case, func

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import db
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency, StatementTitles
from pay_api.utils.util import get_statement_currency_string, get_statement_date_string


def determine_service_provision_status(status_code: str, payment_method: str) -> bool:
    """Determine if service was provided based on invoice status code and payment method."""
    status_code = status_code.upper().replace(" ", "_")
    if status_code in InvoiceStatus.__members__:
        status_enum = InvoiceStatus[status_code]
    else:
        status_enum = next((s for s in InvoiceStatus if s.value == status_code), status_code)

    if status_enum is None:
        return False

    default_statuses = {
        InvoiceStatus.PAID,
        InvoiceStatus.CANCELLED,
        InvoiceStatus.CREDITED,
        InvoiceStatus.REFUND_REQUESTED,
        InvoiceStatus.REFUNDED,
        InvoiceStatus.COMPLETED,
    }

    if status_enum in default_statuses:
        return True

    match payment_method:
        case PaymentMethod.PAD.value:
            return status_enum in {
                InvoiceStatus.APPROVED,
                InvoiceStatus.SETTLEMENT_SCHEDULED,
            }

        case PaymentMethod.EFT.value:
            return status_enum in {
                InvoiceStatus.APPROVED,
                InvoiceStatus.OVERDUE,
            }

        case PaymentMethod.EJV.value:
            return status_enum in {
                InvoiceStatus.APPROVED,
            }

        case PaymentMethod.INTERNAL.value:
            return status_enum in {
                InvoiceStatus.APPROVED,
            }

        case _:
            return False


def build_grouped_invoice_context(invoices: list[dict], statement: dict, statement_summary: dict) -> list[dict]:
    """Build grouped invoice context, with fixed payment method order."""
    grouped = defaultdict(list)
    for inv in invoices:
        method = inv.get("payment_method")
        grouped[method].append(inv)

    grouped_invoices = []
    first_group = True

    for method in [m.value for m in PaymentMethod.Order]:
        if method not in grouped:
            continue

        items = grouped[method]
        transactions = build_transaction_rows(items, method)
        summary = calculate_invoice_summaries(items, method, statement)
        has_staff_payment = False
        if method == PaymentMethod.INTERNAL.value:
            has_staff_payment = any("routing_slip" not in inv or inv["routing_slip"] is None for inv in items)
            statement_header_text = (
                StatementTitles["INTERNAL_STAFF"].value if has_staff_payment else StatementTitles[method].value
            )
        else:
            statement_header_text = StatementTitles[method].value

        method_context = {
            **summary,
            "payment_method": method,
            "total_paid": get_statement_currency_string(sum(Decimal(inv.get("paid", 0)) for inv in items)),
            "transactions": transactions,
            "is_index_0": first_group,
            "statement_header_text": statement_header_text,
            "include_service_provided": any(t.get("service_provided", False) for t in transactions),
        }

        if method == PaymentMethod.EFT.value:
            method_context["amount_owing"] = get_statement_currency_string(statement.get("amount_owing", 0.00))
            if statement.get("is_interim_statement") and statement_summary:
                method_context["latest_payment_date"] = statement_summary.get("latestStatementPaymentDate")
            elif not statement.get("is_interim_statement") and statement_summary:
                method_context["due_date"] = get_statement_date_string(statement_summary.get("dueDate"))

        if method == PaymentMethod.INTERNAL.value:
            method_context["is_staff_payment"] = has_staff_payment

        grouped_invoices.append(method_context)
        first_group = False

    return grouped_invoices


def calculate_invoice_summaries(invoices: list[dict], payment_method: str, statement: dict) -> dict:
    """Calculate invoice summaries for a payment method using database aggregation."""
    invoice_ids = [inv.get("id") for inv in invoices if inv.get("payment_method") == payment_method and inv.get("id")]
    statement_to_date = statement.get("to_date")

    if not invoice_ids:
        return {
            "paid_summary": 0.0,
            "due_summary": 0.0,
            "totals_summary": 0.0,
            "fees_total": 0.0,
            "service_fees_total": 0.0,
            "gst_total": 0.0,
            "refunds_total": 0.0,
            "credits_total": 0.0,
        }

    if payment_method != PaymentMethod.EFT.value:
        # For non-EFT: refund applies if paid == 0 and refund > 0
        refund_condition = case((and_(InvoiceModel.paid == 0, InvoiceModel.refund > 0), InvoiceModel.refund), else_=0)
    else:
        # For EFT: refund applies if paid == 0 and refund > 0 and refund_date <= statement.to_date
        if statement_to_date:
            refund_condition = case(
                (
                    and_(
                        InvoiceModel.paid == 0,
                        InvoiceModel.refund > 0,
                        InvoiceModel.refund_date.isnot(None),
                        InvoiceModel.refund_date <= func.cast(statement_to_date, db.Date),
                    ),
                    InvoiceModel.refund,
                ),
                else_=0,
            )
        else:
            # Fallback if no statement_to_date provided
            refund_condition = case(
                (and_(InvoiceModel.paid == 0, InvoiceModel.refund > 0), InvoiceModel.refund), else_=0
            )
    # Query to get aggregated values for the specific payment method and invoice IDs
    result = (
        db.session.query(
            func.coalesce(func.sum(paid_condition), 0).label("paid_summary"),
            func.coalesce(func.sum(InvoiceModel.total - refund_condition), 0).label("totals_summary"),
            func.coalesce(func.sum(InvoiceModel.total - paid_condition - refund_condition), 0).label("due_summary"),
            func.coalesce(func.sum(InvoiceModel.total - InvoiceModel.service_fees - InvoiceModel.gst), 0).label(
                "fees_total"
            ),
            func.coalesce(func.sum(InvoiceModel.service_fees), 0).label("service_fees_total"),
            func.coalesce(func.sum(InvoiceModel.gst), 0).label("gst_total"),
            func.coalesce(
                func.sum(
                    case(
                        (InvoiceModel.invoice_status_code == InvoiceStatus.REFUNDED.value, InvoiceModel.refund),
                        else_=0,
                    )
                ),
                0,
            ).label("refunds_total"),
            func.coalesce(
                func.sum(
                    case(
                        (InvoiceModel.invoice_status_code == InvoiceStatus.CREDITED.value, InvoiceModel.refund),
                        else_=0,
                    )
                ),
                0,
            ).label("credits_total"),
        ).filter(and_(InvoiceModel.id.in_(invoice_ids), InvoiceModel.payment_method_code == payment_method))
    ).first()

    summary = {k: float(v or 0) for k, v in result._asdict().items()}
    return summary


@dataclass
class TransactionRow:
    """transactions details."""

    products: list[str]
    details: list[str]
    folio: str
    created_on: str
    fee: str
    service_fee: str
    gst: str
    total: str
    extra: dict = field(default_factory=dict)


def build_transaction_rows(
    invoices: list[dict], payment_method: PaymentMethod = None, statement: dict = None
) -> list[dict]:
    """Build transactions for grouped_invoices."""
    rows = []
    for inv in invoices:
        product_lines = []
        for item in inv.get("line_items", []):
            label = "(Cancelled) " if inv.get("status_code") == InvoiceStatus.CANCELLED.value else ""
            product_lines.append(f"{label}{item.get('description', '')}")

        detail_lines = []
        for detail in inv.get("details", []):
            detail_lines.append(f"{detail.get('label', '')} {detail.get('value', '')}")
        fee = max(inv.get("total", 0) - inv.get("service_fees", 0) - inv.get("gst", 0), 0)

        row = TransactionRow(
            products=product_lines,
            details=detail_lines,
            folio=inv.get("folio_number") or "-",
            created_on=get_statement_date_string(
                datetime.fromisoformat(inv["created_on"]).strftime("%b %d,%Y") if inv.get("created_on") else "-"
            ),
            fee=get_statement_currency_string(fee),
            service_fee=get_statement_currency_string(inv.get("service_fees", 0)),
            gst=get_statement_currency_string(inv.get("gst", 0)),
            total=get_statement_currency_string(inv.get("total", 0)),
            extra={
                k: v
                for k, v in inv.items()
                if k
                not in {
                    "details",
                    "folio_number",
                    "created_on",
                    "fee",
                    "gst",
                    "total",
                    "service_fees",
                    "status_code",
                }
            },
        )
        service_provided = False
        if payment_method:
            service_provided = determine_service_provision_status(inv.get("status_code", ""), payment_method)

        row.extra["service_provided"] = service_provided

        row_dict = cattrs.unstructure(row)
        row_dict.update(row_dict.pop("extra"))
        rows.append(row_dict)

    return rows


@dataclass
class StatementContext:
    """A class representing the context of a statement."""

    duration: str | None = None
    amount_owing: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    created_on: str | None = None
    frequency: str | None = None
    extra: dict = field(default_factory=dict)


def build_statement_context(statement: dict) -> dict:
    """Build and enhance statement context with formatted fields."""
    if not statement:
        return statement

    statement_ = statement.copy()

    from_date = get_statement_date_string(statement.get("from_date"))
    to_date = get_statement_date_string(statement.get("to_date"))
    created_on = get_statement_date_string(statement.get("created_on"))
    frequency = statement.get("frequency", "")

    if frequency == StatementFrequency.DAILY.value and from_date:
        duration = from_date
    elif from_date and to_date:
        duration = f"{from_date} - {to_date}"
    elif from_date:
        duration = from_date
    else:
        duration = None

    amount_owing = statement.get("amount_owing")
    amount_owing_str = get_statement_currency_string(amount_owing) if amount_owing else get_statement_currency_string(0)

    enhanced_statement = StatementContext(
        duration=duration,
        amount_owing=amount_owing_str,
        from_date=from_date,
        to_date=to_date,
        created_on=created_on,
        frequency=frequency,
        extra={
            k: v
            for k, v in statement_.items()
            if k not in {"from_date", "to_date", "amount_owing", "created_on", "frequency"}
        },
    )
    enhanced_statement_dict = cattrs.unstructure(enhanced_statement)
    enhanced_statement_dict.update(enhanced_statement_dict.pop("extra"))
    return enhanced_statement_dict


@dataclass
class StatementSummary:
    """A class representing the summary of a statement."""

    last_statement_total: str | None = None
    last_statement_paid_amount: str | None = None
    cancelled_transactions: str | None = None
    latest_statement_payment_date: str | None = None
    due_date: str | None = None
    extra: dict = field(default_factory=dict)


def build_statement_summary_context(statement_summary: dict) -> list[dict]:
    """Build and enhance statement_summary context with formatted fields."""
    if not statement_summary:
        return None

    def currency(v):
        return get_statement_currency_string(v)

    def date(v):
        return get_statement_date_string(v, "%B %d, %Y") if v else None

    handled_keys = {humps.camelize(f.name) for f in fields(StatementSummary)}

    summary_row = StatementSummary(
        last_statement_total=currency(statement_summary.get("lastStatementTotal")),
        last_statement_paid_amount=currency(statement_summary.get("lastStatementPaidAmount")),
        cancelled_transactions=(
            currency(statement_summary["cancelledTransactions"])
            if statement_summary.get("cancelledTransactions") not in [None, 0, "0", "0.00"]
            else None
        ),
        latest_statement_payment_date=date(statement_summary.get("latestStatementPaymentDate")),
        due_date=date(statement_summary.get("dueDate")),
        extra={k: v for k, v in statement_summary.items() if k not in handled_keys},
    )

    summary_row_dict = {humps.camelize(k): v for k, v in cattrs.unstructure(summary_row).items()}
    summary_row_dict.update(summary_row_dict.pop("extra"))
    if summary_row_dict.get("cancelledTransactions") is None:
        summary_row_dict.pop("cancelledTransactions")
    return summary_row_dict


def build_summary_page_context(grouped_invoices: list[dict]) -> dict:
    """Build summary context from grouped_invoices for the summary page.

    Summary page needs context because of chunked rendering in the report API.
    """
    if len(grouped_invoices or []) <= 1:
        return {"display_summary_page": False}

    grouped_summary: list[dict] = []

    summary_fields = ["totals_summary", "due_summary", "refunds_summary", "credits_summary"]

    for invoice in grouped_invoices or []:
        summary_item = {field: invoice.get(field, 0.00) for field in summary_fields}
        payment_method = invoice.get("payment_method")
        summary_item.update(
            {
                "refunds_total": invoice.get("refunds_total", 0.00),
                "credits_total": invoice.get("credits_total", 0.00),
                "refunds_credits_total": invoice.get("refunds_total", 0.00) + invoice.get("credits_total", 0.00),
                "payment_method": CodeService.find_code_value_by_type_and_code(
                    Code.PAYMENT_METHODS.value, payment_method
                ).get("description", payment_method),
            }
        )
        grouped_summary.append(summary_item)

    totals = {field: sum(item[field] for item in grouped_summary) for field in summary_fields}
    totals["refunds_credits_total"] = sum(item["refunds_credits_total"] for item in grouped_summary)

    return {
        "grouped_summary": grouped_summary,
        "display_summary_page": True,
        "total": totals,
    }
