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
from collections import OrderedDict, defaultdict
from datetime import datetime
from decimal import Decimal
from typing import List

from dateutil import parser

from pay_api.utils.enums import PaymentMethod, StatementTitles
from pay_api.utils.util import format_currency, format_datetime


def build_grouped_invoice_context(invoices: List[dict], statement: dict,
                                  statement_summary: dict) -> list[dict]:
    """Build grouped invoice context, with fixed payment method order."""
    grouped = defaultdict(list)
    for inv in invoices:
        method = inv.get("payment_method")
        grouped[method].append(inv)

    result = OrderedDict()
    first_group = True

    for method in [m.value for m in PaymentMethod.Order]:
        if method not in grouped:
            continue

        items = grouped[method]
        method_context = {
            "total_paid": format_currency(sum(Decimal(inv.get("paid", 0)) for inv in items)),
            "transactions": build_transaction_rows(items),
            "is_index_0": first_group
        }

        if method == PaymentMethod.EFT.value:
            method_context["amount_owing"] = format_currency(statement.get("amount_owing", 0.00))
            if statement.get("is_interim_statement") and statement_summary:
                method_context["latest_payment_date"] = statement_summary.get("latestStatementPaymentDate")
            elif not statement.get("is_interim_statement") and statement_summary:
                method_context["due_date"] = format_datetime(statement_summary.get("dueDate"))

        if method == PaymentMethod.INTERNAL.value:
            has_staff_payment = any("routing_slip" not in inv or inv["routing_slip"] is None for inv in items)
            method_context["is_staff_payment"] = has_staff_payment
        else:
            has_staff_payment = False

        summary = calculate_invoice_summaries(items, method, statement)
        statement_header_text = StatementTitles['DEFAULT'].value

        if method == PaymentMethod.INTERNAL.value and has_staff_payment:
            statement_header_text = StatementTitles['INTERNAL_STAFF'].value
        else:
            statement_header_text = StatementTitles[method].value

        method_context.update({
            "paid_summary": summary["paid"],
            "due_summary": summary["due"],
            "totals_summary": summary["total"],
            "statement_header_text": statement_header_text
        })

        result[method] = method_context
        first_group = False

    grouped_invoices = [
        {"payment_method": method, **context}
        for method, context in result.items()
    ]

    return grouped_invoices


def calculate_invoice_summaries(invoices: List[dict], payment_method: str, statement: dict) -> dict:
    """Calculate paid, due, and totals summary for a specific payment method."""
    paid_total, due_total, total_total = 0, 0, 0
    for invoice in invoices:
        if invoice.get("payment_method") != payment_method:
            continue

        paid = Decimal(invoice.get("paid", 0))
        refund = Decimal(invoice.get("refund", 0))
        total = Decimal(invoice.get("total", 0))
        refund_date = invoice.get("refund_date")
        paid_total += paid
        total_total += total
        due_amount = total

        if payment_method != PaymentMethod.EFT.value:
            due_amount -= paid
            if paid == 0 and refund > 0:
                due_amount -= refund
        else:
            due_amount -= paid
            if (
                paid == 0
                and refund > 0
                and refund_date
                and parser.parse(refund_date) <= parser.parse(statement.get("to_date"))
            ):
                due_amount -= refund
        due_total += due_amount

    return {
        "paid": format_currency(paid_total),
        "due": format_currency(due_total),
        "total": format_currency(total_total),
    }


def build_transaction_rows(invoices: List[dict]) -> List[dict]:
    """Build transactions for grouped_invoices."""
    rows = []
    for inv in invoices:
        product_lines = []
        for item in inv.get("line_items", []):
            label = "(Cancelled) " if inv.get("status_code") == "CANCELLED" else ""
            product_lines.append(f"{label}{item.get('description', '')}")

        detail_lines = []
        for detail in inv.get("details", []):
            detail_lines.append(f"{detail.get('label', '')} {detail.get('value', '')}")
        fee = (
            round(inv.get("total", 0) - inv.get("service_fees", 0), 2)
            if inv.get("total") and inv.get("service_fees")
            else 0.00
        )

        service_fee = round(inv.get("service_fees", 0), 2)
        gst = round(inv.get("gst", 0), 2)
        total = round(inv.get("total", 0), 2)

        row = {
            "products": product_lines,
            "details": detail_lines,
            "folio": inv.get("folio_number") or "-",
            "created_on": format_datetime(datetime.fromisoformat(inv["created_on"]).strftime("%b %d,%Y")
                                          if inv.get("created_on") else "-"),
            "fee": format_currency(fee),
            "service_fee": format_currency(service_fee),
            "gst": format_currency(gst),
            "total": format_currency(total),
        }

        skip_keys = {"details", "folio_number", "created_on", "fee", "gst", "total", "service_fees"}
        row.update((k, v) for k, v in inv.items() if k not in skip_keys)
        rows.append(row)

    return rows


def build_statement_context(statement: dict) -> dict:
    """Build and enhance statement context with formatted fields."""
    if not statement:
        return statement

    enhanced_statement = statement.copy()

    from_date = format_datetime(statement.get('from_date'))
    to_date = format_datetime(statement.get('to_date'))
    created_on = format_datetime(statement.get('created_on'))
    frequency = statement.get('frequency', '')

    if frequency == 'DAILY' and from_date:
        enhanced_statement['duration'] = from_date
    elif from_date and to_date:
        enhanced_statement['duration'] = f"{from_date} - {to_date}"
    elif from_date:
        enhanced_statement['duration'] = from_date

    amount_owing = statement.get('amount_owing')
    enhanced_statement['amount_owing'] = format_currency(amount_owing) if amount_owing else format_currency(0)

    if from_date:
        enhanced_statement['from_date'] = from_date
    if to_date:
        enhanced_statement['to_date'] = to_date
    if created_on:
        enhanced_statement['created_on'] = created_on

    return enhanced_statement


def build_statement_summary_context(statement_summary: dict) -> dict:
    """Build and enhance statement_summary context with formatted fields."""
    if not statement_summary:
        return None

    enhanced_statement_summary = statement_summary.copy()

    last_statement_total = statement_summary.get('lastStatementTotal')
    last_statement_paid_amount = statement_summary.get('lastStatementPaidAmount')
    cancelled_transactions = statement_summary.get('cancelledTransactions')
    latest_statement_payment_date = statement_summary.get('latestStatementPaymentDate')
    due_date = statement_summary.get('dueDate')

    enhanced_statement_summary['lastStatementTotal'] = format_currency(last_statement_total)
    enhanced_statement_summary['lastStatementPaidAmount'] = format_currency(last_statement_paid_amount)

    if cancelled_transactions not in [None, 0, '0', '0.00']:
        enhanced_statement_summary['cancelledTransactions'] = format_currency(cancelled_transactions)

    if latest_statement_payment_date:
        enhanced_statement_summary['latestStatementPaymentDate'] = format_datetime(latest_statement_payment_date,
                                                                                   "%B %d, %Y")
    else:
        enhanced_statement_summary['latestStatementPaymentDate'] = None

    enhanced_statement_summary['dueDate'] = format_datetime(due_date, "%B %d, %Y")

    return enhanced_statement_summary
