# Copyright © 2024 Province of British Columbia
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
"""Model to handle all operations related to Invoice."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import pytz
from attrs import define
from dateutil.relativedelta import relativedelta
from marshmallow import fields, post_dump
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from pay_api.models.applied_credits import AppliedCreditsSearchModel
from pay_api.models.payment_line_item import PaymentLineItemSearchModel
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus

from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice_reference import InvoiceReferenceSchema
from .payment_account import PaymentAccountSchema, PaymentAccountSearchModel
from .payment_line_item import PaymentLineItem, PaymentLineItemSchema
from .receipt import ReceiptSchema
from .refunds_partial import RefundPartialSearch


def determine_overdue_date(context):
    """Determine the overdue date with the correct time offset."""
    created_on = context.get_current_parameters()["created_on"]
    target_date = created_on.date() + relativedelta(months=2, day=15)
    target_datetime = datetime.combine(target_date, datetime.min.time())
    # Correct for daylight savings.
    hours = target_datetime.astimezone(pytz.timezone("America/Vancouver")).utcoffset().total_seconds() / 60 / 60
    target_date = target_datetime.replace(tzinfo=timezone.utc) + relativedelta(hours=-hours)
    return target_date.replace(tzinfo=None)


class Invoice(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Invoice."""

    __tablename__ = "invoices"
    # this mapper is used so that new and old versions of the service can be run simultaneously,
    # making rolling upgrades easier
    # This is used by SQLAlchemy to explicitly define which fields we're interested
    # so it doesn't freak out and say it can't map the structure if other fields are present.
    # This could occur from a failed deploy or during an upgrade.
    # The other option is to tell SQLAlchemy to ignore differences, but that is ambiguous
    # and can interfere with Alembic upgrades.
    #
    # NOTE: please keep mapper names in alpha-order, easier to track that way
    #       Exception, id is always first, _fields first
    __mapper_args__ = {
        "include_properties": [
            "id",
            "bcol_account",
            "business_identifier",
            "corp_type_code",
            "created_by",
            "created_name",
            "created_on",
            "cfs_account_id",
            "dat_number",
            "details",
            "disbursement_reversal_date",
            "disbursement_status_code",
            "disbursement_date",
            "filing_id",
            "folio_number",
            "gst",
            "invoice_status_code",
            "payment_account_id",
            "payment_date",
            "payment_method_code",
            "paid",
            "overdue_date",
            "refund",
            "refund_date",
            "routing_slip",
            "service_fees",
            "total",
            "updated_by",
            "updated_name",
            "updated_on",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    invoice_status_code = db.Column(
        db.String(20),
        ForeignKey("invoice_status_codes.code"),
        nullable=False,
        index=True,
    )
    payment_account_id = db.Column(db.Integer, ForeignKey("payment_accounts.id"), nullable=True, index=True)
    cfs_account_id = db.Column(db.Integer, ForeignKey("cfs_accounts.id"), nullable=True)
    payment_method_code = db.Column(db.String(15), ForeignKey("payment_methods.code"), nullable=False, index=True)
    corp_type_code = db.Column(db.String(10), ForeignKey("corp_types.code"), nullable=True)
    disbursement_status_code = db.Column(db.String(20), ForeignKey("disbursement_status_codes.code"), nullable=True)
    disbursement_date = db.Column(db.DateTime, nullable=True)
    disbursement_reversal_date = db.Column(db.DateTime, nullable=True)
    created_on = db.Column(
        "created_on",
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
        index=True,
    )

    business_identifier = db.Column(db.String(20), nullable=True)
    total = db.Column(db.Numeric(19, 2), nullable=False)
    paid = db.Column(db.Numeric(19, 2), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    overdue_date = db.Column(db.DateTime, nullable=True, default=determine_overdue_date)
    refund_date = db.Column(db.DateTime, nullable=True)
    refund = db.Column(db.Numeric(19, 2), nullable=True)
    routing_slip = db.Column(db.String(50), nullable=True, index=True)
    filing_id = db.Column(db.String(50), nullable=True)
    folio_number = db.Column(db.String(50), nullable=True, index=True)
    gst = db.Column(
        db.Numeric(19, 2), nullable=True, comment="Total GST amount including statutory and service fees GST"
    )
    dat_number = db.Column(db.String(50), nullable=True, index=True)
    bcol_account = db.Column(db.String(50), nullable=True, index=True)
    service_fees = db.Column(db.Numeric(19, 2), nullable=True)
    details = db.Column(JSONB)

    payment_line_items = relationship("PaymentLineItem", lazy="joined")
    receipts = relationship("Receipt", lazy="joined")
    payment_account = relationship("PaymentAccount", lazy="joined")
    references = relationship("InvoiceReference", lazy="joined")
    partial_refunds = relationship("RefundsPartial", lazy="joined", order_by="RefundsPartial.id")
    applied_credits = relationship("AppliedCredits", lazy="joined", order_by="AppliedCredits.id")
    corp_type = relationship("CorpType", foreign_keys=[corp_type_code], lazy="select", innerjoin=True)

    __table_args__ = (
        db.Index(
            "idx_invoice_invoice_status_code_payment_account_idx",
            payment_account_id,
            invoice_status_code,
        ),
    )

    @classmethod
    def update_invoices_for_revenue_updates(cls, fee_distribution_id: int):
        """Find and update all invoices using the distribution id."""
        query = (
            db.session.query(Invoice)
            .join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .filter(PaymentLineItem.fee_distribution_id == fee_distribution_id)
        )

        invoices: List[Invoice] = query.all()
        for invoice in invoices:
            if invoice.invoice_status_code == InvoiceStatus.PAID.value:
                invoice.invoice_status_code = InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value
            if invoice.invoice_status_code == InvoiceStatus.REFUNDED.value:
                invoice.invoice_status_code = InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value
        db.session.bulk_save_objects(invoices)
        cls.commit()

    @classmethod
    def find_by_business_identifier(cls, business_identifier: str):
        """Find all payment accounts by business_identifier."""
        return cls.query.filter_by(business_identifier=business_identifier).all()

    @classmethod
    def find_invoices_by_status_for_account(cls, pay_account_id: int, invoice_statuses: List[str]) -> List[Invoice]:
        """Return invoices by status for an account."""
        query = (
            cls.query.filter_by(payment_account_id=pay_account_id)
            .filter(Invoice.invoice_status_code.in_(invoice_statuses))
            .order_by(Invoice.id)
        )

        return query.all()

    @classmethod
    def find_invoices_for_payment(
        cls, payment_id: int, reference_status=InvoiceReferenceStatus.ACTIVE.value
    ) -> List[Invoice]:
        """Find all invoice records created for the payment."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .invoice_reference import InvoiceReference
        from .payment import Payment

        query = (
            db.session.query(Invoice)
            .join(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .join(Payment, InvoiceReference.invoice_number == Payment.invoice_number)
            .filter(InvoiceReference.status_code == reference_status)
            .filter(Payment.id == payment_id)
        )

        return query.all()

    @classmethod
    def find_invoices_marked_for_delete(cls):
        """Return a invoices with status DELETE_ACCEPTED."""
        return cls.query.filter_by(invoice_status_code=InvoiceStatus.DELETE_ACCEPTED.value).all()

    @classmethod
    def find_outstanding_invoices_for_account(cls, pay_account_id: int, from_date: datetime):
        """Return invoices which are in APPROVED status, OR recent (N days) PAD PAID invoices."""
        query = cls.query.filter_by(payment_account_id=pay_account_id).filter(
            (Invoice.invoice_status_code.in_([InvoiceStatus.APPROVED.value, InvoiceStatus.PARTIAL.value]))
            | (
                (Invoice.payment_method_code == PaymentMethod.PAD.value)
                & (Invoice.invoice_status_code == InvoiceStatus.PAID.value)
                & (Invoice.created_on >= from_date)
            )
            | (
                (Invoice.payment_method_code == PaymentMethod.EFT.value)
                & (Invoice.payment_method_code.in_([InvoiceStatus.APPROVED.value, InvoiceStatus.OVERDUE.value]))
                & (Invoice.created_on >= from_date)
            )
        )

        return query.all()

    @classmethod
    def find_created_direct_pay_invoices(cls, days: int = 0, hours: int = 0, minutes: int = 0):
        """Return recent invoices within a certain time and is not complete.

        Used in the batch job to find orphan records which are untouched for a time.
        Removed CC payments cause CC use the get receipt route, not the PAYBC invoice status route
        """
        earliest_transaction_time = datetime.now(tz=timezone.utc) - (timedelta(days=days, hours=hours, minutes=minutes))
        return (
            db.session.query(Invoice)
            .filter(Invoice.invoice_status_code == InvoiceStatus.CREATED.value)
            .filter(Invoice.payment_method_code.in_([PaymentMethod.DIRECT_PAY.value]))
            .filter(Invoice.created_on >= earliest_transaction_time)
            .all()
        )


class InvoiceSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the invoice."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Invoice
        exclude = ["corp_type", "gst"]

    invoice_status_code = fields.String(data_key="status_code")
    corp_type_code = fields.String(data_key="corp_type_code")
    payment_method_code = fields.String(data_key="payment_method")

    # pylint: disable=no-member
    payment_line_items = ma.Nested(PaymentLineItemSchema, many=True, data_key="line_items")
    receipts = ma.Nested(ReceiptSchema, many=True, data_key="receipts")
    references = ma.Nested(InvoiceReferenceSchema, many=True, data_key="references")
    payment_account = ma.Nested(
        PaymentAccountSchema(only=("auth_account_id", "name", "billable", "branch_name")),
        many=False,
    )

    _links = ma.Hyperlinks(
        {
            "self": ma.URLFor("INVOICE.get_invoice", values={"invoice_id": "<id>"}),
            "collection": ma.URLFor("INVOICE.get_invoices", values={"invoice_id": "<id>"}),
        }
    )

    total = fields.Float(data_key="total")
    gst = fields.Float(data_key="gst")
    paid = fields.Float(data_key="paid")
    refund = fields.Float(data_key="refund")
    service_fees = fields.Float(data_key="service_fees")

    @post_dump
    def _clean_up(self, data, many):  # pylint: disable=unused-argument
        """Clean up attributes."""
        # Invoice is always deleted in this scenario:
        if data.get("line_items"):
            for line in list(data.get("line_items")):
                if line.get("status_code") == LineItemStatus.CANCELLED.value:
                    data.get("line_items").remove(line)
                    # It's possible we might need to remove GST fields for CSO.

        if "line_items" in data and not data.get("line_items"):
            data.pop("line_items")

        # do not include temporary business identifier
        if data.get("business_identifier", None) and data.get("business_identifier").startswith("T"):
            data.pop("business_identifier")

        # Adding this here to make non-breaking changes for other teams EG: CSO
        if data.get("status_code") == InvoiceStatus.PAID.value:
            data["status_code"] = PaymentStatus.COMPLETED.value

        return data


@define
class InvoiceSearchModel:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """Main schema used to serialize invoice searches, plus csv / pdf export."""

    # NOTE CSO uses this model for reconciliation, so it needs to follow the spec fairly closely.
    # https://github.com/bcgov/sbc-pay/blob/e722e68450ac28e9c5f3352b10edce2d0388c327/docs/docs/api_contract/pay-api-1.0.3.yaml#L1591

    id: int
    bcol_account: str
    business_identifier: str
    corp_type_code: str
    created_by: str
    created_on: datetime
    paid: Decimal
    refund: Decimal
    service_fees: Decimal
    total: Decimal
    gst: Decimal
    status_code: str
    filing_id: str
    folio_number: str
    payment_method: str
    created_name: str
    details: Optional[List[dict]]
    payment_account: Optional[PaymentAccountSearchModel]
    line_items: Optional[List[PaymentLineItemSearchModel]]
    product: str
    invoice_number: str
    payment_date: datetime
    refund_date: datetime
    disbursement_date: datetime
    disbursement_reversal_date: datetime
    partial_refunds: Optional[List[RefundPartialSearch]]
    applied_credits: Optional[List[AppliedCreditsSearchModel]]

    @classmethod
    def from_row(
        cls,
        row,
    ):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        # Similar to _clean_up in InvoiceSchema.
        # It's possible we might need to remove GST fields for CSO.

        return cls(
            id=row.id,
            bcol_account=row.bcol_account,
            business_identifier=(
                None if row.business_identifier and row.business_identifier.startswith("T") else row.business_identifier
            ),
            corp_type_code=row.corp_type.code,
            created_by=row.created_by,
            created_on=row.created_on,
            paid=row.paid,
            refund=row.refund,
            service_fees=row.service_fees,
            total=row.total,
            gst=row.gst,
            status_code=(
                PaymentStatus.COMPLETED.value
                if row.invoice_status_code == InvoiceStatus.PAID.value
                else row.invoice_status_code
            ),
            filing_id=row.filing_id,
            folio_number=row.folio_number,
            payment_method=row.payment_method_code,
            created_name=row.created_name,
            details=row.details,
            payment_account=PaymentAccountSearchModel.from_row(row.payment_account),
            line_items=[PaymentLineItemSearchModel.from_row(x) for x in row.payment_line_items],
            product=row.corp_type.product,
            payment_date=row.payment_date,
            refund_date=row.refund_date,
            disbursement_date=row.disbursement_date,
            disbursement_reversal_date=row.disbursement_reversal_date,
            invoice_number=row.references[0].invoice_number if len(row.references) > 0 else None,
            # Remove these for CSO, as we don't pull back this information for CSO route.
            partial_refunds=(
                [RefundPartialSearch.from_row(x) for x in row.partial_refunds] if row.partial_refunds else None
            ),
            applied_credits=(
                [AppliedCreditsSearchModel.from_row(x) for x in row.applied_credits] if row.applied_credits else None
            ),
        )
