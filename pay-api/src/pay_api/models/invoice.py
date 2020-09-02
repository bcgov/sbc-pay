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

from marshmallow import fields, post_dump
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from pay_api.utils.enums import InvoiceStatus, LineItemStatus
from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice_reference import InvoiceReferenceSchema
from .payment_line_item import PaymentLineItem, PaymentLineItemSchema
from .receipt import ReceiptSchema


class Invoice(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Invoice."""

    __tablename__ = 'invoice'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.Integer, ForeignKey('payment.id'), nullable=False)

    invoice_status_code = db.Column(db.String(20), ForeignKey('invoice_status_code.code'), nullable=False)
    bcol_account_id = db.Column(db.Integer, ForeignKey('bcol_payment_account.id'), nullable=True)
    internal_account_id = db.Column(db.Integer, ForeignKey('internal_payment_account.id'), nullable=True)
    credit_account_id = db.Column(db.Integer, ForeignKey('credit_payment_account.id'), nullable=True)

    corp_type_code = db.Column(db.String(10), ForeignKey('corp_type.code'), nullable=True)
    business_identifier = db.Column(db.String(20), nullable=True)

    total = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Float, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    refund = db.Column(db.Float, nullable=True)
    routing_slip = db.Column(db.String(50), nullable=True)
    filing_id = db.Column(db.String(50), nullable=True)
    folio_number = db.Column(db.String(50), nullable=True, index=True)
    dat_number = db.Column(db.String(50), nullable=True, index=True)
    service_fees = db.Column(db.Float, nullable=True)

    payment_line_items = relationship('PaymentLineItem')
    receipts = relationship('Receipt')

    bcol_account = relationship('BcolPaymentAccount')
    internal_account = relationship('InternalPaymentAccount')
    credit_account = relationship('CreditPaymentAccount')

    references = relationship('InvoiceReference')

    @classmethod
    def find_by_payment_id(cls, identifier: int):
        """Return a Invoice by id."""
        return cls.query.filter_by(payment_id=identifier).one_or_none()

    @classmethod
    def find_by_id_and_payment_id(cls, identifier: int, pay_id: int):
        """Return a Invoice by id."""
        return cls.query.filter_by(payment_id=pay_id).filter_by(id=identifier).one_or_none()

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
        db.session.bulk_save_objects(invoices)
        cls.commit()


class InvoiceSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the invoice."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Invoice
        exclude = ['bcol_account', 'internal_account', 'credit_account']

    invoice_status_code = fields.String(data_key='status_code')
    corp_type_code = fields.String(data_key='corp_type_code')

    # pylint: disable=no-member
    payment_line_items = ma.Nested(PaymentLineItemSchema, many=True, data_key='line_items')
    receipts = ma.Nested(ReceiptSchema, many=True, data_key='receipts')
    references = ma.Nested(InvoiceReferenceSchema, many=True, data_key='references')

    _links = ma.Hyperlinks({
        'self': ma.URLFor('API.invoices_invoice', payment_id='<payment_id>', invoice_id='<id>'),
        'collection': ma.URLFor('API.invoices_invoices', payment_id='<payment_id>')
    })

    @post_dump
    def _remove_deleted_lines(self, data, many):  # pylint: disable=unused-argument,no-self-use
        if data.get('line_items'):
            for line in list(data.get('line_items')):
                if line.get('status_code') == LineItemStatus.CANCELLED.value:
                    data.get('line_items').remove(line)

        if 'line_items' in data and not data.get('line_items'):
            data.pop('line_items')

        # do not include temproary business identifier
        if data.get('business_identifier', None) and data.get('business_identifier').startswith('T'):
            data.pop('business_identifier')

        return data
