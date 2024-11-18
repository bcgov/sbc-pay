"""Serializable class for cattr structure and unstructure."""

from pay_api.models import db
from pay_api.models.fee_schedule import FeeSchedule
from pay_api.models.invoice import Invoice
from pay_api.models.invoice_reference import InvoiceReference
from pay_api.models.payment_account import PaymentAccount
from pay_api.models.payment_line_item import PaymentLineItem
from pay_api.utils.converter import Converter
from pay_api.utils.enums import TransactionsViewColumns
from sqlalchemy.orm import contains_eager, lazyload, load_only, relationship


class Serializable:
    """Helper for cattr structure and unstructure (serialization/deserialization)."""

    @classmethod
    def from_dict(cls, data: dict):
        """Convert from dictionary to object."""
        return Converter(camel_to_snake_case=True).structure(data, cls)

    def to_dict(self):
        """Convert from object to dictionary."""
        return Converter(snake_case_to_camel=True).unstructure(self)

    @classmethod
    def generate_base_transaction_query(cls):
        """Generate a base query matching the structure of the Transactions materialized view."""
        return (
            db.session.query(Invoice)
            .outerjoin(PaymentAccount, Invoice.payment_account_id == PaymentAccount.id)
            .outerjoin(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .outerjoin(
                FeeSchedule,
                FeeSchedule.fee_schedule_id == PaymentLineItem.fee_schedule_id,
            )
            .outerjoin(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .options(
                lazyload("*"),
                load_only(
                    Invoice.id,
                    Invoice.corp_type_code,
                    Invoice.created_on,
                    Invoice.payment_date,
                    Invoice.refund_date,
                    Invoice.invoice_status_code,
                    Invoice.total,
                    Invoice.service_fees,
                    Invoice.paid,
                    Invoice.refund,
                    Invoice.folio_number,
                    Invoice.created_name,
                    Invoice.invoice_status_code,
                    Invoice.payment_method_code,
                    Invoice.details,
                    Invoice.business_identifier,
                    Invoice.created_by,
                    Invoice.filing_id,
                    Invoice.bcol_account,
                    Invoice.disbursement_date,
                    Invoice.disbursement_reversal_date,
                    Invoice.overdue_date,
                ),
                contains_eager(Invoice.payment_line_items)
                .load_only(
                    PaymentLineItem.description,
                    PaymentLineItem.gst,
                    PaymentLineItem.pst,
                )
                .contains_eager(PaymentLineItem.fee_schedule)
                .load_only(FeeSchedule.filing_type_code),
                contains_eager(Invoice.payment_account).load_only(
                    PaymentAccount.auth_account_id,
                    PaymentAccount.name,
                    PaymentAccount.billable,
                ),
                contains_eager(Invoice.references).load_only(
                    InvoiceReference.invoice_number,
                    InvoiceReference.reference_number,
                    InvoiceReference.status_code,
                )
            )
        )
