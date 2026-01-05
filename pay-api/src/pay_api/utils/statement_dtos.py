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

from collections import defaultdict
from datetime import datetime  # noqa: TC001 TC003
from decimal import Decimal  # noqa: TC001 TC003

from attrs import define

from pay_api.models.applied_credits import AppliedCreditsSearchModel
from pay_api.models.invoice import Invoice as InvoiceModel  # noqa: TC001
from pay_api.models.payment_line_item import PaymentLineItemSearchModel
from pay_api.models.statement import Statement  # noqa: TC001 TC003
from pay_api.utils.converter import CurrencyStr, FullMonthDateStr
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, RefundsPartialType, StatementFrequency, StatementTitles
from pay_api.utils.serializable import Serializable


@define
class StatementTransactionDTO(Serializable):
    """DTO for a single invoice transaction in PDF statement.

    Represents a formatted transaction row with all display-ready values.
    """

    invoice_id: int
    products: list[str]
    details: list[str]
    folio: str
    status_code: str
    service_provided: bool
    line_items: list[PaymentLineItemSearchModel]
    created_on: FullMonthDateStr
    fee: CurrencyStr
    service_fee: CurrencyStr
    gst: CurrencyStr
    total: CurrencyStr
    is_full_applied_credits: bool
    applied_credits_amount: CurrencyStr
    refund_total: CurrencyStr
    refund_fee: CurrencyStr
    refund_gst: CurrencyStr
    refund_service_fee: CurrencyStr
    payment_date: FullMonthDateStr | None
    refund_date: FullMonthDateStr | None
    refund_id: str | None = None
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
            InvoiceStatus.PARTIALLY_CREDITED.value,
            InvoiceStatus.PARTIALLY_REFUNDED.value,
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

    @staticmethod
    def _compute_refund_lines_for_display(invoice: InvoiceModel, fee: Decimal):
        """Compute refund lines for display in statement."""
        if invoice.invoice_status_code not in InvoiceStatus.refund_statuses():
            return 0, 0, 0, None

        if invoice.invoice_status_code in InvoiceStatus.partial_fund_statuses():
            base_partial = sum(
                r.refund_amount for r in invoice.partial_refunds if r.refund_type == RefundsPartialType.BASE_FEES.value
            )
            service_partial = sum(
                r.refund_amount
                for r in invoice.partial_refunds
                if r.refund_type == RefundsPartialType.SERVICE_FEES.value
            )
            gst_partial = invoice.refund - base_partial - service_partial
            refund_id = ",".join(str(r.id) for r in invoice.partial_refunds)
            return base_partial, gst_partial, service_partial, refund_id

        return fee, invoice.gst, invoice.service_fees, invoice.refund_id

    @classmethod
    def from_orm(
        cls,
        invoice: InvoiceModel,
        payment_method: str,
        statement_to_date: datetime,
    ) -> StatementTransactionDTO:
        """Create DTO from ORM invoice object for PDF statement."""
        products = [item.description for item in invoice.payment_line_items]
        details = [f"{d.get('label', '')} {d.get('value', '')}".strip() for d in (invoice.details or [])]
        fee = invoice.total - invoice.service_fees - (invoice.gst or 0)
        status_code = invoice.invoice_status_code
        service_provided = cls.determine_service_provision_status(status_code, payment_method)
        line_items = [PaymentLineItemSearchModel.from_row(item) for item in invoice.payment_line_items]

        applied_credits = None
        applied_credits_amount = 0
        if invoice.applied_credits:
            # Convert date to datetime for comparison
            statement_to_datetime = datetime.combine(statement_to_date, datetime.max.time())
            filtered_credits = [c for c in invoice.applied_credits if c.created_on <= statement_to_datetime]
            if filtered_credits:
                applied_credits = [AppliedCreditsSearchModel.from_row(c) for c in filtered_credits]
                applied_credits_amount = sum((c.amount_applied for c in filtered_credits), Decimal("0"))

        is_full_applied_credits = applied_credits_amount == invoice.total

        refund_fee, refund_gst, refund_service_fee, refund_id = cls._compute_refund_lines_for_display(invoice, fee)

        return cls(
            invoice_id=invoice.id,
            products=products,
            details=details,
            folio=invoice.folio_number or "-",
            created_on=FullMonthDateStr(invoice.created_on),
            fee=fee,
            service_fee=invoice.service_fees,
            gst=invoice.gst,
            total=invoice.total,
            status_code=status_code,
            service_provided=service_provided,
            line_items=line_items,
            payment_date=FullMonthDateStr(invoice.payment_date),
            refund_date=FullMonthDateStr(invoice.refund_date),
            applied_credits=applied_credits,
            applied_credits_amount=CurrencyStr(applied_credits_amount),
            is_full_applied_credits=is_full_applied_credits,
            refund_id=refund_id,
            refund_fee=CurrencyStr(refund_fee),
            refund_gst=CurrencyStr(refund_gst),
            refund_service_fee=CurrencyStr(refund_service_fee),
            refund_total=CurrencyStr(invoice.refund),
        )


@define
class PaymentMethodSummaryDTO(Serializable):
    """DTO for payment method summary totals in PDF statement."""

    totals: CurrencyStr
    fees: CurrencyStr
    service_fees: CurrencyStr
    gst: CurrencyStr
    paid: CurrencyStr
    due: CurrencyStr
    credits_applied: CurrencyStr | None = None
    counted_refund: CurrencyStr | None = None

    @classmethod
    def from_db_summary(cls, db_summary: PaymentMethodSummaryRawDTO) -> PaymentMethodSummaryDTO:
        """Create from database aggregation summary for PDF statement."""
        if db_summary is None:
            return cls(
                totals=0.00,
                fees=0.00,
                service_fees=0.00,
                gst=0.00,
                paid=0.00,
                due=0.00,
                counted_refund=0.00,
                credits_applied=0.00,
            )
        return cls(
            totals=db_summary.totals,
            fees=db_summary.fees,
            service_fees=db_summary.service_fees,
            gst=db_summary.gst,
            paid=db_summary.paid,
            due=db_summary.due,
            credits_applied=db_summary.credits_applied,
            counted_refund=db_summary.counted_refund,
        )


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
    PAID_PRE_BALANCE = "paid_pre_balance"
    COUNTED_REFUND = "counted_refund"
    CREDITS_APPLIED = "credits_applied"
    INVOICE_COUNT = "invoice_count"
    IS_PRE_SUMMARY = "is_pre_summary"
    PAYMENT_METHOD = "payment_method_code"

    totals: Decimal
    fees: Decimal
    service_fees: Decimal
    gst: Decimal
    paid: Decimal
    due: Decimal
    credits_applied: Decimal
    counted_refund: Decimal
    invoice_count: int
    is_pre_summary: bool | None = None
    paid_pre_balance: Decimal | None = None
    latest_payment_date: FullMonthDateStr | None = None

    @classmethod
    def from_db_row(cls, row) -> PaymentMethodSummaryRawDTO:
        """Create from database query row."""
        totals = getattr(row, cls.TOTALS)
        counted_refund = getattr(row, cls.COUNTED_REFUND)
        credits_applied = getattr(row, cls.CREDITS_APPLIED)
        paid = getattr(row, cls.PAID)
        is_pre_summary = getattr(row, cls.IS_PRE_SUMMARY) or False
        paid_pre_balance = getattr(row, cls.PAID_PRE_BALANCE) or 0
        payment_method = getattr(row, cls.PAYMENT_METHOD, None)

        # For EFT, PAD, and ONLINE_BANKING, refunds are kept as credits in the account
        refund_as_credit_methods = {
            PaymentMethod.EFT.value,
            PaymentMethod.PAD.value,
            PaymentMethod.ONLINE_BANKING.value,
        }

        if payment_method in refund_as_credit_methods:
            net_total = totals - credits_applied - counted_refund
            net_paid = paid - credits_applied
            net_due = net_total - net_paid
        else:
            net_total = totals - credits_applied - counted_refund
            net_paid = paid
            net_due = totals - paid

        paid_redefined = paid_pre_balance if is_pre_summary else net_paid

        return cls(
            totals=net_total,
            fees=getattr(row, cls.FEES),
            service_fees=getattr(row, cls.SERVICE_FEES),
            gst=getattr(row, cls.GST),
            credits_applied=credits_applied,
            counted_refund=counted_refund,
            paid=paid_redefined,
            due=net_due,
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
    credits_applied: CurrencyStr | None = None
    counted_refund: CurrencyStr | None = None
    statement_summary: StatementSummaryDTO | None = None
    # EFT-specific fields
    amount_owing: CurrencyStr | None = None
    latest_payment_date: str | None = None
    due_date: FullMonthDateStr | None = None
    # INTERNAL-specific fields
    is_staff_payment: bool | None = None

    @classmethod
    def from_invoices_and_summary(
        cls,
        payment_method: str,
        invoices_orm: list[InvoiceModel],
        db_summary: PaymentMethodSummaryRawDTO,
        statement: Statement,
        statement_summary: StatementSummaryDTO | None,
        statement_to_date: datetime,
        is_first: bool = False,
    ) -> GroupedInvoicesDTO:
        """Create DTO from ORM invoices and database summary for PDF statement."""
        transactions = [
            t
            for t in (StatementTransactionDTO.from_orm(inv, payment_method, statement_to_date) for inv in invoices_orm)
            if t.service_provided
        ]

        summary = PaymentMethodSummaryDTO.from_db_summary(db_summary)
        include_service_provided = any(t.service_provided for t in transactions)

        adjusted_due = summary.due
        if statement_summary and hasattr(statement_summary, "balance_forward"):
            adjusted_due = adjusted_due + Decimal(statement_summary.balance_forward) + summary.credits_applied

        # Compute payment method specific fields before instantiation
        # INTERNAL-specific: header text and staff payment flag
        is_staff_payment = None
        if payment_method == PaymentMethod.INTERNAL.value:
            is_staff_payment = any(not hasattr(inv, "routing_slip") or inv.routing_slip is None for inv in invoices_orm)
            statement_header_text = (
                StatementTitles.INTERNAL_STAFF.value if is_staff_payment else StatementTitles[payment_method].value
            )
        else:
            statement_header_text = StatementTitles[payment_method].value

        # EFT-specific: amount owing and dates
        amount_owing = None
        latest_payment_date = None
        due_date = None
        if payment_method == PaymentMethod.EFT.value:
            amount_owing = statement.amount_owing
            if statement.is_interim_statement and statement_summary:
                latest_payment_date = statement_summary.get("latestStatementPaymentDate")
            elif not statement.is_interim_statement and statement_summary:
                due_date = FullMonthDateStr(statement_summary.get("dueDate"))

        return cls(
            payment_method=payment_method,
            totals=summary.totals,
            fees=summary.fees,
            service_fees=summary.service_fees,
            gst=summary.gst,
            paid=summary.paid,
            due=adjusted_due,
            credits_applied=summary.credits_applied,
            counted_refund=summary.counted_refund,
            statement_summary=statement_summary,
            transactions=transactions,
            is_index_0=is_first,
            statement_header_text=statement_header_text,
            include_service_provided=include_service_provided,
            amount_owing=amount_owing,
            latest_payment_date=latest_payment_date,
            due_date=due_date,
            is_staff_payment=is_staff_payment,
        )


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
    notification_date: FullMonthDateStr | None = None
    payment_methods: list[str] | None = None
    statement_total: CurrencyStr | None = None
    is_overdue: bool | None = None
    pad_credit: Decimal | None = None
    eft_credit: Decimal | None = None
    ob_credit: Decimal | None = None

    @staticmethod
    def _compute_duration(from_date: str | None, to_date: str | None, frequency: str) -> str | None:
        """Compute duration string based on dates and frequency."""
        if not from_date:
            return None

        if frequency == StatementFrequency.DAILY.value:
            return FullMonthDateStr(from_date)

        if to_date:
            return f"{FullMonthDateStr(from_date)} - {FullMonthDateStr(to_date)}"

        return FullMonthDateStr(from_date)

    @classmethod
    def from_statement(cls, statement) -> StatementContextDTO:
        """Create DTO from Statement object."""
        if not statement:
            return None

        duration = cls._compute_duration(statement.from_date, statement.to_date, statement.frequency or "")

        # Convert the comma-separated payment_methods string (e.g., "EFT,PAD") into a list.
        # The DTO expects a list[str], and without this conversion the Converter in converter.py
        # would treat the string as an iterable and split it into individual characters
        payment_methods = None
        if statement.payment_methods:
            payment_methods = [m.strip() for m in statement.payment_methods.split(",") if m.strip()]

        # Directly assign formatted string values
        return cls(
            duration=duration,
            amount_owing=statement.amount_owing,
            from_date=FullMonthDateStr(statement.from_date),
            to_date=FullMonthDateStr(statement.to_date),
            created_on=FullMonthDateStr(statement.created_on),
            frequency=statement.frequency or "",
            id=statement.id,
            is_interim_statement=statement.is_interim_statement,
            overdue_notification_date=FullMonthDateStr(statement.overdue_notification_date),
            notification_date=FullMonthDateStr(statement.notification_date),
            payment_methods=payment_methods,
            statement_total=statement.statement_total,
            is_overdue=statement.is_overdue,
            pad_credit=statement.pad_credit,
            eft_credit=statement.eft_credit,
            ob_credit=statement.ob_credit,
        )

    @classmethod
    def from_dict(cls, statement: dict) -> StatementContextDTO:
        """Create DTO from statement dictionary with formatting."""
        if not statement:
            return None

        from_date = statement.get("from_date")
        to_date = statement.get("to_date")
        frequency = statement.get("frequency", "")

        duration = cls._compute_duration(from_date, to_date, frequency)

        return cls(
            duration=duration,
            amount_owing=statement.get("amount_owing"),
            from_date=from_date,
            to_date=to_date,
            created_on=statement.get("created_on"),
            frequency=frequency,
            id=statement.get("id"),
            is_interim_statement=statement.get("is_interim_statement"),
            overdue_notification_date=statement.get("overdue_notification_date"),
            notification_date=statement.get("notification_date"),
            payment_methods=statement.get("payment_methods"),
            statement_total=statement.get("statement_total"),
            is_overdue=statement.get("is_overdue"),
            pad_credit=statement.get("pad_credit"),
            eft_credit=statement.get("eft_credit"),
            ob_credit=statement.get("ob_credit"),
        )


@define
class StatementSummaryDTO(Serializable):
    """DTO for statement summary for a payment method."""

    last_statement_total: CurrencyStr
    last_statement_paid_amount: CurrencyStr
    balance_forward: CurrencyStr
    cancelled_transactions: CurrencyStr | None = None
    latest_statement_payment_date: FullMonthDateStr | None = None
    due_date: FullMonthDateStr | None = None
    credit_balance: CurrencyStr | None = None

    @classmethod
    def from_dict(cls, statement_summary: dict) -> StatementSummaryDTO:
        """Create DTO from statement_summary dictionary with formatting."""
        if not statement_summary:
            return None

        # Handle zero cancelled transactions - convert to None
        cancelled_transactions = statement_summary.get("cancelledTransactions")
        if cancelled_transactions == 0:
            cancelled_transactions = None

        return cls(
            last_statement_total=statement_summary.get("lastStatementTotal"),
            last_statement_paid_amount=statement_summary.get("lastStatementPaidAmount"),
            cancelled_transactions=cancelled_transactions,
            latest_statement_payment_date=FullMonthDateStr(statement_summary.get("latestStatementPaymentDate")),
            due_date=FullMonthDateStr(statement_summary.get("dueDate")),
            balance_forward=statement_summary.get("balanceForward") or 0,
            credit_balance=statement_summary.get("creditBalance"),
        )


@define
class StatementSummaryTotal(Serializable):
    """DTO for statement summary grouped by payment method (for PDF rendering)."""

    summaries: defaultdict[str, StatementSummaryDTO]

    @classmethod
    def from_dict(cls, data: dict) -> StatementSummaryTotal:
        """Expected input shape:
        {
            "PAD": { ... },
            "EFT": { ... },
            "ONLINE_BANKING": { ... }
        }
        """
        if not data:
            return cls(summaries={})

        summaries: defaultdict[PaymentMethod, StatementSummaryDTO] = {}

        for method, summary_dict in data.items():
            ss = StatementSummaryDTO.from_dict(summary_dict)
            if ss:
                summaries[method] = ss

        return cls(summaries=summaries)

    def get(self, payment_method: PaymentMethod | str) -> StatementSummaryDTO | None:
        """Convenience accessor."""
        key = payment_method.value if isinstance(payment_method, PaymentMethod) else payment_method
        return self.summaries.get(key)


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

    def get_summary(self, payment_method: str) -> PaymentMethodSummaryRawDTO:
        """Get summary DTO for a specific payment method."""
        return self.summaries.get(payment_method)

    def get_all_payment_methods(self) -> list[str]:
        """Get list of all payment methods in summaries."""
        return list(self.summaries.keys())


@define
class StatementPDFContextDTO(Serializable):
    """DTO for complete PDF statement rendering context."""

    grouped_invoices: list[GroupedInvoicesDTO]
    account: dict | None
    statement: StatementContextDTO
    has_payment_instructions: bool = False
