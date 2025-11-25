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

from dataclasses import dataclass
from datetime import datetime

import cattrs

from pay_api.models.invoice import Invoice
from pay_api.utils.enums import PaymentMethod, StatementTitles
from pay_api.utils.util import get_statement_currency_string, get_statement_date_string


@dataclass
class StatementTransactionDTO:
    """DTO for a single invoice transaction in PDF statement.

    Represents a formatted transaction row with all display-ready values.
    """

    products: list[str]
    details: list[str]
    folio: str
    created_on: str
    fee: str
    service_fee: str
    gst: str
    total: str
    status_code: str
    service_provided: bool
    payment_date: str | None = None
    refund_date: str | None = None

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

        # avoid circular dependency
        from pay_api.services.invoice_search import InvoiceSearch

        status_code = InvoiceSearch._adjust_invoice_status_for_statement_orm(invoice, payment_method, statement_to_date)

        service_provided = InvoiceSearch.determine_service_provision_status(invoice.invoice_status_code, payment_method)

        return cls(
            products=products,
            details=details,
            folio=invoice.folio_number or "-",
            created_on=get_statement_date_string(invoice.created_on, "%b %d, %Y"),
            fee=get_statement_currency_string(fee),
            service_fee=get_statement_currency_string(invoice.service_fees),
            gst=get_statement_currency_string(invoice.gst or 0),
            total=get_statement_currency_string(invoice.total),
            status_code=status_code,
            service_provided=service_provided,
            payment_date=get_statement_date_string(invoice.payment_date, "%b %d, %Y") or None,
            refund_date=get_statement_date_string(invoice.refund_date, "%b %d, %Y") or None,
        )


@dataclass
class PaymentMethodSummaryDTO:
    """DTO for payment method summary totals in PDF statement."""

    totals: str
    fees: str
    service_fees: str
    gst: str
    paid: str
    due: str

    @classmethod
    def from_db_summary(cls, db_summary: PaymentMethodSummaryRawDTO | None) -> PaymentMethodSummaryDTO:
        """Create from database aggregation summary for PDF statement."""
        fields = ["totals", "fees", "service_fees", "gst", "paid", "due"]
        source = db_summary or type("", (), {f: 0 for f in fields})()
        return cls(**{f: get_statement_currency_string(getattr(source, f)) for f in fields})


@dataclass
class PaymentMethodSummaryRawDTO:
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

    totals: float
    fees: float
    service_fees: float
    gst: float
    paid: float
    due: float
    invoice_count: int

    @classmethod
    def from_db_row(cls, row) -> PaymentMethodSummaryRawDTO:
        """Create from database query row."""
        totals = float(getattr(row, cls.TOTALS))
        paid = float(getattr(row, cls.PAID))
        counted_refund = float(getattr(row, cls.COUNTED_REFUND))

        due = totals - paid - counted_refund

        return cls(
            totals=totals,
            fees=float(getattr(row, cls.FEES)),
            service_fees=float(getattr(row, cls.SERVICE_FEES)),
            gst=float(getattr(row, cls.GST)),
            paid=paid,
            due=due,
            invoice_count=getattr(row, cls.INVOICE_COUNT),
        )


@dataclass
class GroupedInvoicesDTO:
    """DTO for invoices grouped by payment method in PDF statement."""

    payment_method: str
    totals: str
    fees: str
    service_fees: str
    gst: str
    paid: str
    due: str
    transactions: list[StatementTransactionDTO]
    is_index_0: bool
    statement_header_text: str = None
    include_service_provided: bool = False
    # EFT-specific fields
    amount_owing: str = None
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

        dto = cls(
            payment_method=payment_method,
            totals=summary.totals,
            fees=summary.fees,
            service_fees=summary.service_fees,
            gst=summary.gst,
            paid=summary.paid,
            due=summary.due,
            transactions=transactions,
            is_index_0=is_first,
            statement_header_text=statement_header_text,
            include_service_provided=include_service_provided,
        )

        if payment_method == PaymentMethod.EFT.value:
            dto.amount_owing = get_statement_currency_string(statement.get("amount_owing", 0.0))
            if statement.get("is_interim_statement") and statement_summary:
                dto.latest_payment_date = statement_summary.get("latestStatementPaymentDate")
            elif not statement.get("is_interim_statement") and statement_summary:
                dto.due_date = get_statement_date_string(statement_summary.get("dueDate"))

        if payment_method == PaymentMethod.INTERNAL.value:
            dto.is_staff_payment = any(
                not hasattr(inv, "routing_slip") or inv.routing_slip is None for inv in invoices_orm
            )

        return dto


@dataclass
class StatementTotalsDTO:
    """DTO for overall statement totals across all payment methods in PDF statement."""

    fees: str
    service_fees: str
    gst: str
    totals: str
    paid: str
    due: str

    @classmethod
    def from_db_summaries(cls, db_summaries: dict[str, PaymentMethodSummaryRawDTO]) -> StatementTotalsDTO:
        """Create DTO from multiple payment method summaries for PDF statement.

        db_summaries: Dict with payment_method as key
        """
        fields = ["fees", "service_fees", "gst", "totals", "paid", "due"]
        totals = {field: sum(getattr(s, field) for s in db_summaries.values()) for field in fields}
        return cls(**{field: get_statement_currency_string(totals[field]) for field in fields})


@dataclass
class StatementContextDTO:
    """DTO for statement metadata in PDF rendering."""

    duration: str | None = None
    amount_owing: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    created_on: str | None = None
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

        from pay_api.utils.enums import StatementFrequency

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
        amount_owing_str = (
            get_statement_currency_string(amount_owing) if amount_owing else get_statement_currency_string(0)
        )

        return cls(
            duration=duration,
            amount_owing=amount_owing_str,
            from_date=from_date,
            to_date=to_date,
            created_on=created_on,
            frequency=frequency,
            id=statement.get("id"),
            is_interim_statement=statement.get("is_interim_statement"),
            overdue_notification_date=statement.get("overdue_notification_date"),
            notification_date=statement.get("notification_date"),
            payment_methods=statement.get("payment_methods"),
            statement_total=statement.get("statement_total"),
            is_overdue=statement.get("is_overdue"),
        )


@dataclass
class StatementSummaryDTO:
    """DTO for statement summary in PDF rendering."""

    last_statement_total: str | None = None
    last_statement_paid_amount: str | None = None
    cancelled_transactions: str | None = None
    latest_statement_payment_date: str | None = None
    due_date: str | None = None
    # Additional fields that might be in statement_summary
    last_pad_statement_paid_amount: float | None = None

    @classmethod
    def from_dict(cls, statement_summary: dict) -> StatementSummaryDTO:
        """Create DTO from statement_summary dictionary with formatting."""
        if not statement_summary:
            return None

        cancelled_transactions = statement_summary.get("cancelledTransactions")
        cancelled_transactions_str = (
            get_statement_currency_string(cancelled_transactions)
            if cancelled_transactions not in [None, 0, "0", "0.00"]
            else None
        )

        return cls(
            last_statement_total=get_statement_currency_string(statement_summary.get("lastStatementTotal")),
            last_statement_paid_amount=get_statement_currency_string(statement_summary.get("lastStatementPaidAmount")),
            cancelled_transactions=cancelled_transactions_str,
            latest_statement_payment_date=get_statement_date_string(
                statement_summary.get("latestStatementPaymentDate"), "%B %d, %Y"
            )
            if statement_summary.get("latestStatementPaymentDate")
            else None,
            due_date=get_statement_date_string(statement_summary.get("dueDate"), "%B %d, %Y")
            if statement_summary.get("dueDate")
            else None,
            last_pad_statement_paid_amount=statement_summary.get("lastPADStatementPaidAmount"),
        )


@dataclass
class SummariesGroupedByPaymentMethodDTO:
    """DTO for payment method summaries from database aggregation.
    Key: payment_method (e.g., 'EFT', 'PAD', 'INTERNAL')
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


@dataclass
class StatementPDFContextDTO:
    """DTO for complete PDF statement rendering context."""

    statement_summary: StatementSummaryDTO | None
    grouped_invoices: list[GroupedInvoicesDTO]
    total: StatementTotalsDTO
    account: dict | None
    statement: StatementContextDTO
    has_payment_instructions: bool = False

    def to_dict(self) -> dict:
        """Convert DTO to dictionary for template rendering."""
        return cattrs.unstructure(self)
