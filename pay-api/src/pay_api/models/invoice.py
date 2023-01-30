# Copyright © 2019 Province of British Columbia
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

from datetime import datetime
from typing import List

from marshmallow import fields, post_dump
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus

from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice_reference import InvoiceReferenceSchema
from .payment_account import PaymentAccountSchema
from .payment_line_item import PaymentLineItem, PaymentLineItemSchema
from .receipt import ReceiptSchema


class Invoice(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Invoice."""

    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    invoice_status_code = db.Column(db.String(20), ForeignKey('invoice_status_codes.code'), nullable=False)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)
    cfs_account_id = db.Column(db.Integer, ForeignKey('cfs_accounts.id'), nullable=True)
    payment_method_code = db.Column(db.String(15), ForeignKey('payment_methods.code'), nullable=False, index=True)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_types.code'), nullable=True)
    disbursement_status_code = db.Column(db.String(20), ForeignKey('disbursement_status_codes.code'), nullable=True)
    disbursement_date = db.Column(db.DateTime, nullable=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now, index=True)

    business_identifier = db.Column(db.String(20), nullable=True)
    total = db.Column(db.Numeric(19, 2), nullable=False)
    paid = db.Column(db.Numeric(19, 2), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    refund = db.Column(db.Numeric(19, 2), nullable=True)
    routing_slip = db.Column(db.String(50), nullable=True, index=True)
    filing_id = db.Column(db.String(50), nullable=True)
    folio_number = db.Column(db.String(50), nullable=True, index=True)
    dat_number = db.Column(db.String(50), nullable=True, index=True)
    bcol_account = db.Column(db.String(50), nullable=True, index=True)
    service_fees = db.Column(db.Numeric(19, 2), nullable=True)
    details = db.Column(JSONB)

    payment_line_items = relationship('PaymentLineItem', lazy='joined')
    receipts = relationship('Receipt', lazy='joined')
    payment_account = relationship('PaymentAccount', lazy='joined')
    references = relationship('InvoiceReference', lazy='joined')

    @classmethod
    def update_invoices_for_revenue_updates(cls, fee_distribution_id: int):
        """Find and update all invoices using the distribution id."""
        query = db.session.query(Invoice) \
            .join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id) \
            .filter(PaymentLineItem.fee_distribution_id == fee_distribution_id)

        invoices: [Invoice] = query.all()
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
    def find_invoices_for_payment(cls, payment_id: int) -> List[Invoice]:
        """Find all invoice records created for the payment."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .invoice_reference import InvoiceReference
        from .payment import Payment

        query = db.session.query(Invoice) \
            .join(InvoiceReference, InvoiceReference.invoice_id == Invoice.id) \
            .join(Payment, InvoiceReference.invoice_number == Payment.invoice_number) \
            .filter(InvoiceReference.status_code == InvoiceReferenceStatus.ACTIVE.value) \
            .filter(Payment.id == payment_id)

        return query.all()

    @classmethod
    def find_invoices_marked_for_delete(cls):
        """Return a invoices with status DELETE_ACCEPTED."""
        return cls.query.filter_by(invoice_status_code=InvoiceStatus.DELETE_ACCEPTED.value).all()

    @classmethod
    def find_outstanding_invoices_for_account(cls, pay_account_id: int, from_date: datetime):
        """Return invoices which are in APPROVED status, OR recent (N days) PAD PAID invoices."""
        query = cls.query.filter_by(payment_account_id=pay_account_id). \
            filter(
            (Invoice.invoice_status_code.in_([InvoiceStatus.APPROVED.value, InvoiceStatus.PARTIAL.value])) |
            (
                    (Invoice.payment_method_code == PaymentMethod.PAD.value) &
                    (Invoice.invoice_status_code == InvoiceStatus.PAID.value) &
                    (Invoice.created_on >= from_date)
            )
        )

        return query.all()


class InvoiceSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the invoice."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Invoice
        exclude = []

    invoice_status_code = fields.String(data_key='status_code')
    corp_type_code = fields.String(data_key='corp_type_code')
    payment_method_code = fields.String(data_key='payment_method')

    # pylint: disable=no-member
    payment_line_items = ma.Nested(PaymentLineItemSchema, many=True, data_key='line_items')
    receipts = ma.Nested(ReceiptSchema, many=True, data_key='receipts')
    references = ma.Nested(InvoiceReferenceSchema, many=True, data_key='references')
    payment_account = ma.Nested(PaymentAccountSchema(only=('auth_account_id', 'name', 'billable')), many=False)

    _links = ma.Hyperlinks({
        'self': ma.URLFor('API.invoice_invoice', invoice_id='<id>'),
        'collection': ma.URLFor('API.invoice_invoices', invoice_id='<id>')
    })

    total = fields.Float(data_key='total')
    paid = fields.Float(data_key='paid')
    refund = fields.Float(data_key='refund')
    service_fees = fields.Float(data_key='service_fees')

    @post_dump
    def _clean_up(self, data, many):  # pylint: disable=unused-argument
        """Clean up attributes."""
        if data.get('line_items'):
            for line in list(data.get('line_items')):
                if line.get('status_code') == LineItemStatus.CANCELLED.value:
                    data.get('line_items').remove(line)

        if 'line_items' in data and not data.get('line_items'):
            data.pop('line_items')

        # do not include temporary business identifier
        if data.get('business_identifier', None) and data.get('business_identifier').startswith('T'):
            data.pop('business_identifier')

        # TODO remove it later, adding this here to make non-breaking changes for other teams
        if data.get('status_code') == InvoiceStatus.PAID.value:
            data['status_code'] = PaymentStatus.COMPLETED.value

        return data
