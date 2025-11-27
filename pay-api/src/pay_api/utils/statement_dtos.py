# Copyright © 2025 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Data Transfer Objects (DTOs) for PDF Statement generation.

This module contains all DTOs used in the statement PDF generation process.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from attrs import define
from dateutil import parser

from pay_api.models.applied_credits import AppliedCreditsSearchModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.payment_line_item import PaymentLineItemSearchModel
from pay_api.utils.converter import Converter, CurrencyStr, FullMonthDateStr
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency, StatementTitles
from pay_api.utils.serializable import Serializable
from pay_api.utils.util import get_statement_date_string

if TYPE_CHECKING:
    from pay_api.models.invoice import Invoice


@define
class StatementTransactionDTO(Serializable):
    """DTO for a single invoice transaction in PDF statement.

    Represents a formatted transaction row with all display-ready values.
    """

    id: int
    products: list[str]
    details: list[str]
    folio: str
    created_on: FullMonthDateStr
    fee: CurrencyStr
    service_fee: CurrencyStr
    gst: CurrencyStr
    total: CurrencyStr
    status_code: str
    service_provided: bool
    line_items: list[PaymentLineItemSearchModel]
    payment_date: FullMonthDateStr | None = None
    refund_date: FullMonthDateStr | None = None
    applied_credits: list[AppliedCreditsSearchModel] | None = None

    @staticmethod
    def determine_service_provision_status(status_code: str, payment_method: str) -> bool:
        """Determine if service was provided based on invoice status code and payment method."""
        default_statuses = {
            InvoiceStatus.PAID.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.CREDITED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.COMPLETED.value,
        }

        if status_code in default_statuses:
            return True

        match payment_method:
            case PaymentMethod.PAD.value:
                return status_code in {
                    InvoiceStatus.APPROVED.value,
                    InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                }

            case PaymentMethod.EFT.value:
                return status_code in {
                    InvoiceStatus.APPROVED.value,
                    InvoiceStatus.OVERDUE.value,
                }

            case PaymentMethod.EJV.value:
                return status_code in {
                    InvoiceStatus.APPROVED.value,
                }

            case PaymentMethod.INTERNAL.value:
                return status_code in {
                    InvoiceStatus.APPROVED.value,
                }

            case _:
                return False

    @classmethod
    def from_orm(
        cls,
        invoice: Invoice,
        payment_method: str,
        statement_to_date: datetime,
    ) -> StatementTransactionDTO:
        """Create DTO from ORM invoice object for PDF statement."""
        products = [item.description for item in invoice.payment_line_items]

        details = [f"{d.get('label')} {d.get('value')}" for d in (invoice.details or [])]

        # statutory fee
        fee = invoice.total - invoice.service_fees - (invoice.gst or 0)

        status_code = invoice.invoice_status_code

        service_provided = cls.determine_service_provision_status(status_code, payment_method)

        line_items = [
            Converter().unstructure(PaymentLineItemSearchModel.from_row(item)) for item in invoice.payment_line_items
        ]

        applied_credits = None
        if invoice.applied_credits:
            filtered_credits = [
                c
                for c in invoice.applied_credits
                if (c.created_on if isinstance(c.created_on, datetime) else parser.parse(c.created_on))
                <= statement_to_date
            ]
            if filtered_credits:
                applied_credits = [
                    Converter().unstructure(AppliedCreditsSearchModel.from_row(c)) for c in filtered_credits
                ]

        data = {
            'id': invoice.id,
            'products': products,
            'details': details,
            'folio': invoice.folio_number or "-",
            'created_on': invoice.created_on,
            'fee': fee,
            'service_fee': invoice.service_fees,
            'gst': invoice.gst,
            'total': invoice.total,
            'status_code': status_code,
            'service_provided': service_provided,
            'line_items': line_items,
            'payment_date': invoice.payment_date,
            'refund_date': invoice.refund_date,
            'applied_credits': applied_credits,
        }
        
        return Converter().structure(data, cls)


@define
class PaymentMethodSummaryDTO(Serializable):
    """DTO for payment method summary totals in PDF statement."""

    totals: CurrencyStr
    fees: CurrencyStr
    service_fees: CurrencyStr
    gst: CurrencyStr
    paid: CurrencyStr
    due: CurrencyStr

    @classmethod
    def from_db_summary(cls, db_summary: PaymentMethodSummaryRawDTO) -> PaymentMethodSummaryDTO:
        """Create from database aggregation summary for PDF statement."""
        data = {
            'totals': db_summary.totals,
            'fees': db_summary.fees,
            'service_fees': db_summary.service_fees,
            'gst': db_summary.gst,
            'paid': db_summary.paid,
            'due': db_summary.due,
        }
        
        return Converter().structure(data, cls)


@define
class PaymentMethodSummaryRawDTO(Serializable):
    """DTO for raw payment method summary from database aggregation.

    This represents the raw numeric values from database queries,
    before formatting for display.
    """

    # Field name constants - used by SQL queries to ensure consistency
    TOTALS = "totals"
    FEES = "fees"
    SERVICE_FEES = "service_fees"
    GST = "gst"
    PAID = "paid"
    COUNTED_REFUND = "counted_refund"
    INVOICE_COUNT = "invoice_count"

    totals: Decimal
    fees: Decimal
    service_fees: Decimal
    gst: Decimal
    paid: Decimal
    due: Decimal
    invoice_count: int

    @classmethod
    def from_db_row(cls, row) -> PaymentMethodSummaryRawDTO:
        """Create from database query row."""
        totals = Decimal(str(getattr(row, cls.TOTALS)))
        paid = Decimal(str(getattr(row, cls.PAID)))
        counted_refund = Decimal(str(getattr(row, cls.COUNTED_REFUND)))

        due = totals - paid - counted_refund

        return cls(
            totals=totals,
            fees=Decimal(str(getattr(row, cls.FEES))),
            service_fees=Decimal(str(getattr(row, cls.SERVICE_FEES))),
            gst=Decimal(str(getattr(row, cls.GST))),
            paid=paid,
            due=due,
            invoice_count=getattr(row, cls.INVOICE_COUNT),
        )


@define
class GroupedInvoicesDTO(Serializable):
    """DTO for invoices grouped by payment method in PDF statement."""

    payment_method: str
    totals: CurrencyStr
    fees: CurrencyStr
    service_fees: CurrencyStr
    gst: CurrencyStr
    paid: CurrencyStr
    due: CurrencyStr
    transactions: list[StatementTransactionDTO]
    is_index_0: bool
    statement_header_text: str = None
    include_service_provided: bool = False
    # EFT-specific fields
    amount_owing: CurrencyStr = None
    latest_payment_date: str = None
    due_date: str = None
    # INTERNAL-specific fields
    is_staff_payment: bool = None

    @classmethod
    def from_invoices_and_summary(
        cls,
        payment_method: str,
        invoices_orm: list[Invoice],
        db_summary: PaymentMethodSummaryRawDTO | None,
        statement: dict,
        statement_summary: dict,
        statement_to_date: datetime,
        is_first: bool = False,
    ) -> GroupedInvoicesDTO:
        """Create DTO from ORM invoices and database summary for PDF statement."""
        transactions = [
            StatementTransactionDTO.from_orm(inv, payment_method, statement_to_date) for inv in invoices_orm
        ]

        summary = PaymentMethodSummaryDTO.from_db_summary(db_summary)

        include_service_provided = any(t.service_provided for t in transactions)

        if payment_method == PaymentMethod.INTERNAL.value:
            has_staff_payment = any(
                not hasattr(inv, "routing_slip") or inv.routing_slip is None for inv in invoices_orm
            )
            statement_header_text = (
                StatementTitles["INTERNAL_STAFF"].value if has_staff_payment else StatementTitles[payment_method].value
            )
        else:
            statement_header_text = StatementTitles[payment_method].value

        data = {
            'payment_method': payment_method,
            'totals': summary.totals,  # CurrencyStr (已转换)
            'fees': summary.fees,
            'service_fees': summary.service_fees,
            'gst': summary.gst,
            'paid': summary.paid,
            'due': summary.due,
            'transactions': transactions,
            'is_index_0': is_first,
            'statement_header_text': statement_header_text,
            'include_service_provided': include_service_provided,
        }

        if payment_method == PaymentMethod.EFT.value:
            data['amount_owing'] = statement.get("amount_owing", 0.0)  # -> CurrencyStr
            if statement.get("is_interim_statement") and statement_summary:
                data['latest_payment_date'] = statement_summary.get("latestStatementPaymentDate")
            elif not statement.get("is_interim_statement") and statement_summary:
                data['due_date'] = statement_summary.get("dueDate")

        if payment_method == PaymentMethod.INTERNAL.value:
            data['is_staff_payment'] = any(
                not hasattr(inv, "routing_slip") or inv.routing_slip is None for inv in invoices_orm
            )
        
        return cls(**data)


@define
class StatementTotalsDTO(Serializable):
    """DTO for overall statement totals across all payment methods in PDF statement."""

    fees: CurrencyStr
    service_fees: CurrencyStr
    gst: CurrencyStr
    totals: CurrencyStr
    paid: CurrencyStr
    due: CurrencyStr

    @classmethod
    def from_db_summaries(cls, db_summaries: dict[str, PaymentMethodSummaryRawDTO]) -> StatementTotalsDTO:
        """Create DTO from multiple payment method summaries for PDF statement.

        db_summaries: Dict with payment_method as key
        """
        fields = ["fees", "service_fees", "gst", "totals", "paid", "due"]
        totals = {field: sum(getattr(s, field) for s in db_summaries.values()) for field in fields}
        return Converter().structure(totals, cls)


@define
class StatementContextDTO(Serializable):
    """DTO for statement metadata in PDF rendering."""

    duration: str | None = None
    amount_owing: CurrencyStr | None = None
    from_date: FullMonthDateStr | None = None
    to_date: FullMonthDateStr | None = None
    created_on: FullMonthDateStr | None = None
    frequency: str | None = None
    # Store extra fields that don't have explicit attributes
    id: int | None = None
    is_interim_statement: bool | None = None
    overdue_notification_date: str | None = None
    notification_date: str | None = None
    payment_methods: list[str] | None = None
    statement_total: float | None = None
    is_overdue: bool | None = None

    @classmethod
    def from_dict(cls, statement: dict) -> StatementContextDTO:
        """Create DTO from statement dictionary with formatting."""
        if not statement:
            return None

        from_date = statement.get("from_date")
        to_date = statement.get("to_date")
        created_on = statement.get("created_on")
        frequency = statement.get("frequency", "")

        if frequency == StatementFrequency.DAILY.value and from_date:
            duration = from_date
        elif from_date and to_date:
            from_date_str = from_date
            to_date_str = to_date
            duration = f"{from_date_str} - {to_date_str}"
        elif from_date:
            duration = from_date
        else:
            duration = None

        data = {
            'duration': duration,
            'amount_owing': statement.get("amount_owing"),
            'from_date': from_date,
            'to_date': to_date,
            'created_on': created_on,
            'frequency': frequency,
            'id': statement.get("id"),
            'is_interim_statement': statement.get("is_interim_statement"),
            'overdue_notification_date': statement.get("overdue_notification_date"),
            'notification_date': statement.get("notification_date"),
            'payment_methods': statement.get("payment_methods"),
            'statement_total': statement.get("statement_total"),
            'is_overdue': statement.get("is_overdue"),
        }
        
        return Converter().structure(data, cls)


@define
class StatementSummaryDTO(Serializable):
    """DTO for statement summary in PDF rendering."""

    last_statement_total: CurrencyStr | None = None
    last_statement_paid_amount: CurrencyStr | None = None
    cancelled_transactions: CurrencyStr | None = None
    latest_statement_payment_date: FullMonthDateStr | None = None
    due_date: FullMonthDateStr | None = None
    # Additional fields that might be in statement_summary
    last_pad_statement_paid_amount: CurrencyStr | None = None

    @classmethod
    def from_dict(cls, statement_summary: dict) -> StatementSummaryDTO:
        """Create DTO from statement_summary dictionary with formatting."""
        if not statement_summary:
            return None

        cancelled_transactions = statement_summary.get("cancelledTransactions")
        cancelled_transactions_formatted = (
            cancelled_transactions if cancelled_transactions not in [None, 0, "0", "0.00"] else None
        )

        data = {
            'last_statement_total': statement_summary.get("lastStatementTotal") or None,
            'last_statement_paid_amount': statement_summary.get("lastStatementPaidAmount") or None,
            'cancelled_transactions': cancelled_transactions_formatted,
            'latest_statement_payment_date': statement_summary.get("latestStatementPaymentDate"),
            'due_date': statement_summary.get("dueDate"),
            'last_pad_statement_paid_amount': statement_summary.get("lastPADStatementPaidAmount"),
        }
        
        return Converter().structure(data, cls)


@define
class SummariesGroupedByPaymentMethodDTO(Serializable):
    """DTO for payment method summaries from database aggregation.

    Key: payment_method (e.g., 'EFT', 'PAD', 'INTERNAL').
    """

    summaries: dict[str, PaymentMethodSummaryRawDTO]

    @classmethod
    def from_db_result(cls, db_summaries: dict[str, PaymentMethodSummaryRawDTO]) -> SummariesGroupedByPaymentMethodDTO:
        """Create from database aggregation result."""
        return cls(summaries=db_summaries)

    def get_summary(self, payment_method: str) -> PaymentMethodSummaryRawDTO | None:
        """Get summary DTO for a specific payment method."""
        return self.summaries.get(payment_method)

    def get_all_payment_methods(self) -> list[str]:
        """Get list of all payment methods in summaries."""
        return list(self.summaries.keys())


@define
class StatementPDFContextDTO(Serializable):
    """DTO for complete PDF statement rendering context."""

    statement_summary: StatementSummaryDTO | None
    grouped_invoices: list[GroupedInvoicesDTO]
    total: StatementTotalsDTO
    account: dict | None
    statement: StatementContextDTO
    has_payment_instructions: bool = False
