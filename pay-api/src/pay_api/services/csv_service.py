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
"""Service to support CSV report generation."""

import csv
import io
from collections.abc import Iterator

from sqlalchemy import and_, case, distinct, func, literal
from sqlalchemy.orm import Query

from pay_api.models import (
    AppliedCredits,
    CorpType,
    Credit,
    FeeSchedule,
    Invoice,
    InvoiceReference,
    InvoiceStatusCode,
    PaymentLineItem,
    Refund,
    RefundsPartial,
    db,
)
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, RefundStatus


class CsvService:
    """Service to support CSV report generation."""

    @staticmethod
    def _get_csv_labels():
        """Get CSV column labels."""
        return [
            "Product",
            "Corp Type",
            "Transaction Type",
            "Transaction",
            "Transaction Details",
            "Folio Number",
            "Initiated By",
            "Date",
            "Purchase Amount",
            "GST",
            "Statutory Fee",
            "BCOL Fee",
            "Status",
            "Corp Number",
            "Transaction ID",
            "Invoice Reference Number",
            "Refund",
            "Applied Credits",
            "Account Credits",
        ]

    @staticmethod
    def _get_formatted_date_expression():
        """Get formatted date expression for CSV."""
        return func.to_char(
            func.timezone("America/Los_Angeles", func.timezone("UTC", Invoice.created_on)), "YYYY-MM-DD HH12:MI:SS AM"
        ).op("||")(literal(" Pacific Time"))

    @staticmethod
    def _process_invoice_details(details: list) -> str:
        """Process invoice details to format and remove duplicates."""
        # Done because it's JSONB and not easy for the database to aggregate them. I've tried for hours.
        # Please use the database for all other operations, no point in using the API to format the data.
        if not details:
            return ""

        seen = set()
        detail_texts = []
        for detail in details:
            detail_text = f"{detail.get('label', '')} {detail.get('value', '')}".strip()
            if detail_text and detail_text not in seen:
                seen.add(detail_text)
                detail_texts.append(detail_text)

        return ",".join(detail_texts) if detail_texts else ""

    @staticmethod
    def _get_approved_refunds_cte(invoice_ids_cte):
        """Get CTE for approved refunds filtered by invoice IDs."""
        return (
            db.session.query(
                Refund.invoice_id,
                func.max(Refund.requested_date).label("latest_refund_date"),
            )
            .filter(Refund.invoice_id.in_(db.session.query(invoice_ids_cte.c.id)))
            .filter(
                Refund.status.in_(
                    [
                        RefundStatus.APPROVED.value,
                        RefundStatus.APPROVAL_NOT_REQUIRED.value,
                    ]
                )
            )
            .group_by(Refund.invoice_id)
            .cte("approved_refunds_cte")
        )

    @staticmethod
    def _get_partial_refunds_status_cte(invoice_ids_cte):
        """Get CTE for partial refunds status filtered by invoice IDs."""
        return (
            db.session.query(
                RefundsPartial.invoice_id,
                func.bool_or(RefundsPartial.is_credit).label("is_credit"),
            )
            .join(Refund, Refund.id == RefundsPartial.refund_id)
            .filter(RefundsPartial.invoice_id.in_(db.session.query(invoice_ids_cte.c.id)))
            .filter(
                Refund.status.in_(
                    [
                        RefundStatus.APPROVED.value,
                        RefundStatus.PENDING_APPROVAL.value,
                        RefundStatus.APPROVAL_NOT_REQUIRED.value,
                    ]
                )
            )
            .group_by(RefundsPartial.invoice_id)
            .cte("partial_refunds_cte")
        )

    @staticmethod
    def _get_applied_credits_cte(invoice_ids_cte):
        """Get CTE for applied credits filtered by invoice IDs."""
        return (
            db.session.query(
                AppliedCredits.invoice_id,
                func.sum(AppliedCredits.amount_applied).label("total_applied_credits"),
            )
            .filter(AppliedCredits.invoice_id.in_(db.session.query(invoice_ids_cte.c.id)))
            .group_by(AppliedCredits.invoice_id)
            .cte("applied_credits_cte")
        )

    @staticmethod
    def _get_credits_received_cte(invoice_ids_cte):
        """Get CTE for credits received filtered by invoice IDs."""
        return (
            db.session.query(
                Credit.created_invoice_id,
                func.sum(Credit.amount).label("total_credits_received"),
            )
            .filter(Credit.created_invoice_id.in_(db.session.query(invoice_ids_cte.c.id)))
            .group_by(Credit.created_invoice_id)
            .cte("credits_received_cte")
        )

    @staticmethod
    def _process_csv_rows(rows: list, details_index: int = 4) -> list:
        """Process CSV rows and handle invoice details formatting."""
        values = []
        for row in rows:
            row_list = list(row)
            if len(row_list) > details_index:
                row_list[details_index] = CsvService._process_invoice_details(row_list[details_index] or [])
            values.append(row_list)
        return values

    @staticmethod
    def prepare_csv_data(results_query: Query) -> dict:
        """Prepare data for creating a CSV report."""
        formatted_date = CsvService._get_formatted_date_expression()
        labels = CsvService._get_csv_labels()

        invoice_ids_cte = results_query.with_entities(Invoice.id).distinct().cte("invoice_ids_cte")

        approved_refunds_cte = CsvService._get_approved_refunds_cte(invoice_ids_cte)
        partial_refunds_cte = CsvService._get_partial_refunds_status_cte(invoice_ids_cte)
        applied_credits_cte = CsvService._get_applied_credits_cte(invoice_ids_cte)
        credits_received_cte = CsvService._get_credits_received_cte(invoice_ids_cte)
        # Build query from scratch with explicit joins to avoid cartesian product warnings
        # Apply filters first, then joins for better performance
        query = (
            db.session.query(invoice_ids_cte)
            .join(Invoice, Invoice.id == invoice_ids_cte.c.id)
            .filter(Invoice.invoice_status_code != InvoiceStatus.DELETED.value)
            .join(CorpType, CorpType.code == Invoice.corp_type_code)
            .join(
                InvoiceStatusCode,
                InvoiceStatusCode.code == Invoice.invoice_status_code,
            )
            .join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .join(
                FeeSchedule,
                FeeSchedule.fee_schedule_id == PaymentLineItem.fee_schedule_id,
            )
            .outerjoin(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .outerjoin(approved_refunds_cte, approved_refunds_cte.c.invoice_id == Invoice.id)
            .outerjoin(partial_refunds_cte, partial_refunds_cte.c.invoice_id == Invoice.id)
            .outerjoin(applied_credits_cte, applied_credits_cte.c.invoice_id == Invoice.id)
            .outerjoin(credits_received_cte, credits_received_cte.c.created_invoice_id == Invoice.id)
            .with_entities(
                CorpType.product,
                Invoice.corp_type_code,
                func.string_agg(distinct(FeeSchedule.filing_type_code), ",").label("filing_type_codes"),
                func.string_agg(distinct(PaymentLineItem.description), ",").label("descriptions"),
                Invoice.details,
                Invoice.folio_number,
                Invoice.created_name,
                formatted_date.label("created_on_formatted"),
                Invoice.total,
                (
                    func.sum(PaymentLineItem.statutory_fees_gst + PaymentLineItem.service_fees_gst)
                    + func.sum(PaymentLineItem.pst)
                ).label("total_tax"),
                (Invoice.total - func.coalesce(Invoice.service_fees, 0)).label("statutory_fee"),
                func.coalesce(Invoice.service_fees, 0).label("service_fee"),
                case(
                    (
                        and_(
                            Invoice.invoice_status_code == InvoiceStatus.PAID.value,
                            Invoice.refund != 0,
                            Invoice.refund_date.isnot(None),
                            partial_refunds_cte.c.is_credit.isnot(None),
                        ),
                        case(
                            (partial_refunds_cte.c.is_credit.is_(True), literal("Partially Credited")),
                            else_=literal("Partially Refunded"),
                        ),
                    ),
                    (
                        and_(
                            Invoice.payment_method_code == PaymentMethod.PAD.value,
                            Invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                        ),
                        literal("Non Sufficient Funds"),
                    ),
                    (
                        and_(
                            Invoice.payment_method_code == PaymentMethod.ONLINE_BANKING.value,
                            Invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                        ),
                        literal("Pending"),
                    ),
                    (
                        Invoice.invoice_status_code == InvoiceStatus.PAID.value,
                        literal("COMPLETED"),
                    ),
                    else_=InvoiceStatusCode.description,
                ).label("invoice_status_code"),
                case(
                    (Invoice.business_identifier.like("T%"), literal("")),
                    else_=Invoice.business_identifier,
                ).label("business_identifier"),
                Invoice.id,
                func.string_agg(distinct(InvoiceReference.invoice_number), ",").label("invoice_number"),
                (
                    -case(
                        (
                            approved_refunds_cte.c.latest_refund_date.isnot(None),
                            func.coalesce(Invoice.refund, 0),
                        ),
                        else_=literal(0),
                    )
                ).label("total_refund"),
                func.coalesce(applied_credits_cte.c.total_applied_credits, 0).label("total_applied_credits"),
                (-func.coalesce(credits_received_cte.c.total_credits_received, 0)).label("total_credits_received"),
            )
            .group_by(
                CorpType.product,
                Invoice.corp_type_code,
                Invoice.folio_number,
                Invoice.created_name,
                Invoice.created_on,
                Invoice.total,
                Invoice.service_fees,
                Invoice.invoice_status_code,
                InvoiceStatusCode.description,
                Invoice.business_identifier,
                Invoice.id,
                Invoice.refund,
                Invoice.refund_date,
                Invoice.payment_method_code,
                approved_refunds_cte.c.latest_refund_date,
                partial_refunds_cte.c.is_credit,
                applied_credits_cte.c.total_applied_credits,
                credits_received_cte.c.total_credits_received,
            )
            .order_by(Invoice.id.desc())
        )

        rows = query.all()
        values = CsvService._process_csv_rows(rows)

        return {
            "columns": labels,
            "values": values,
        }

    @classmethod
    def create_report(cls, payload: dict) -> Iterator[bytes]:
        """Create a streaming CSV report generator from the input parameters."""
        columns = payload.get("columns", None)
        values = payload.get("values", None)
        if not columns:
            return

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(columns)
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)

        for row in values:
            writer.writerow(row)
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)
