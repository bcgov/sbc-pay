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
"""Model to handle all operations related to Payment data."""

from datetime import datetime
from typing import Dict

from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy import or_
from sqlalchemy.orm import relationship

from pay_api.utils.enums import PaymentStatus
from pay_api.utils.util import get_first_and_last_dates_of_month, get_str_by_path, get_week_start_and_end_date
from .audit import Audit
from .base_schema import BaseSchema
from .bcol_payment_account import BcolPaymentAccount
from .credit_payment_account import CreditPaymentAccount
from .db import db, ma
from .internal_payment_account import InternalPaymentAccount
from .invoice import Invoice
from .invoice import InvoiceSchema
from .payment_account import PaymentAccount
from .payment_method import PaymentMethod
from .payment_system import PaymentSystem
from .payment_status_code import PaymentStatusCode
from .payment_transaction import PaymentTransactionSchema


class Payment(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment ."""

    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_system_code = db.Column(db.String(10), ForeignKey('payment_system.code'), nullable=False)
    payment_method_code = db.Column(db.String(10), ForeignKey('payment_method.code'), nullable=False)
    payment_status_code = db.Column(db.String(20), ForeignKey('payment_status_code.code'), nullable=False)

    payment_system = relationship(PaymentSystem, foreign_keys=[payment_system_code], lazy='select', innerjoin=True)
    payment_status = relationship(PaymentStatusCode, foreign_keys=[payment_status_code], lazy='select', innerjoin=True)
    invoices = relationship('Invoice')
    transactions = relationship('PaymentTransaction')

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Payment by id."""
        return cls.query.get(identifier)

    @classmethod
    def find_payment_method_by_payment_id(cls, identifier: int):
        """Return a Payment by id."""
        query = db.session.query(PaymentMethod) \
            .join(Payment) \
            .filter(PaymentMethod.code == Payment.payment_method_code) \
            .filter(Payment.id == identifier)
        return query.one_or_none()

    @classmethod
    def search_purchase_history(cls, auth_account_id: str, search_filter: Dict,  # pylint:disable=too-many-arguments
                                page: int, limit: int, return_all: bool):
        """Search for purchase history."""
        # Payment Account Sub Query
        payment_account_sub_query = db.session.query(PaymentAccount).filter(
            PaymentAccount.auth_account_id == auth_account_id).subquery('pay_accnt')

        query = db.session.query(Payment, Invoice) \
            .join(Invoice) \
            .outerjoin(CreditPaymentAccount) \
            .outerjoin(BcolPaymentAccount) \
            .outerjoin(InternalPaymentAccount) \
            .filter(or_(InternalPaymentAccount.account_id == payment_account_sub_query.c.id,
                        BcolPaymentAccount.account_id == payment_account_sub_query.c.id,
                        CreditPaymentAccount.account_id == payment_account_sub_query.c.id))

        if search_filter.get('status', None):
            query = query.filter(Payment.payment_status_code == search_filter.get('status'))
        if search_filter.get('folioNumber', None):
            query = query.filter(Invoice.folio_number == search_filter.get('folioNumber'))
        if search_filter.get('businessIdentifier', None):
            query = query.filter(Invoice.business_identifier == search_filter.get('businessIdentifier'))
        if search_filter.get('createdBy', None):  # pylint: disable=no-member
            query = query.filter(
                Payment.created_name.like('%' + search_filter.get('createdBy') + '%'))  # pylint: disable=no-member

        # Find start and end dates
        created_from: datetime = None
        created_to: datetime = None
        if get_str_by_path(search_filter, 'dateFilter/startDate'):
            created_from = datetime.strptime(get_str_by_path(search_filter, 'dateFilter/startDate'), '%m/%d/%Y')
        if get_str_by_path(search_filter, 'dateFilter/endDate'):
            created_to = datetime.strptime(get_str_by_path(search_filter, 'dateFilter/endDate'), '%m/%d/%Y')
        if get_str_by_path(search_filter, 'weekFilter/index'):
            created_from, created_to = get_week_start_and_end_date(
                int(get_str_by_path(search_filter, 'weekFilter/index')))
        if get_str_by_path(search_filter, 'monthFilter/month') and get_str_by_path(search_filter, 'monthFilter/year'):
            month = int(get_str_by_path(search_filter, 'monthFilter/month'))
            year = int(get_str_by_path(search_filter, 'monthFilter/year'))
            created_from, created_to = get_first_and_last_dates_of_month(month=month, year=year)

        if created_from and created_to:
            # Truncate time for from date and add max time for to date
            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(Payment.created_on.between(created_from, created_to))

        # Add ordering
        query = query.order_by(Payment.created_on.desc())

        if not return_all:
            # Add pagination
            pagination = query.paginate(per_page=limit, page=page)
            result, count = pagination.items, pagination.total
        else:
            result = query.all()
            count = len(result)

        return result, count

    @classmethod
    def find_payments_marked_for_delete(cls):
        """Return a Payment by id."""
        return cls.query.filter_by(payment_status_code=PaymentStatus.DELETE_ACCEPTED.value).all()


class PaymentSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Payment
        exclude = ['payment_system', 'payment_status']

    payment_system_code = fields.String(data_key='payment_system')
    payment_method_code = fields.String(data_key='payment_method')
    payment_status_code = fields.String(data_key='status_code')

    # pylint: disable=no-member
    invoices = ma.Nested(InvoiceSchema, many=True, exclude=('payment_line_items', 'receipts'))
    transactions = ma.Nested(PaymentTransactionSchema, many=True)

    _links = ma.Hyperlinks({
        'self': ma.URLFor('API.payments_payments', payment_id='<id>'),
        'collection': ma.URLFor('API.payments_payment'),
        'invoices': ma.URLFor('API.invoices_invoices', payment_id='<id>'),
        'transactions': ma.URLFor('API.transactions_transaction', payment_id='<id>')
    })
