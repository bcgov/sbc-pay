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

import pytz
from flask import current_app
from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship

from pay_api.utils.enums import PaymentStatus
from pay_api.utils.util import get_first_and_last_dates_of_month, get_str_by_path, get_week_start_and_end_date
from .audit import Audit, AuditSchema
from .db import db, ma
from .invoice import Invoice
from .invoice import InvoiceSchema
from .payment_account import PaymentAccount
from .payment_method import PaymentMethod
from .payment_status_code import PaymentStatusCode
from .payment_system import PaymentSystem
from .payment_transaction import PaymentTransactionSchema
from .base_schema import BaseSchema


class Payment(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment ."""

    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_system_code = db.Column(db.String(10), ForeignKey('payment_system.code'), nullable=False)
    payment_method_code = db.Column(db.String(15), ForeignKey('payment_method.code'), nullable=False)
    payment_status_code = db.Column(db.String(20), ForeignKey('payment_status_code.code'), nullable=False)

    payment_system = relationship(PaymentSystem, foreign_keys=[payment_system_code], lazy='select', innerjoin=True)
    payment_status = relationship(PaymentStatusCode, foreign_keys=[payment_status_code], lazy='select', innerjoin=True)
    invoices = relationship('Invoice')
    transactions = relationship('PaymentTransaction')

    @classmethod
    def find_payment_method_by_payment_id(cls, identifier: int):
        """Return a Payment by id."""
        query = db.session.query(PaymentMethod) \
            .join(Payment) \
            .filter(PaymentMethod.code == Payment.payment_method_code) \
            .filter(Payment.id == identifier)
        return query.one_or_none()

    @classmethod
    def search_purchase_history(cls,  # pylint:disable=too-many-arguments, too-many-locals, too-many-branches
                                auth_account_id: str, search_filter: Dict,
                                page: int, limit: int, return_all: bool, max_no_records: int = 0):
        """Search for purchase history."""
        # Payment Account Sub Query
        # payment_account_sub_query = db.session.query(PaymentAccount).filter(
        #     PaymentAccount.auth_account_id == auth_account_id).subquery('pay_accnt')

        query = db.session.query(Payment, Invoice) \
            .join(Invoice) \
            .outerjoin(PaymentAccount, Invoice.payment_account_id == PaymentAccount.id) \
            .filter(PaymentAccount.auth_account_id == auth_account_id)

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
            tz_name = current_app.config['LEGISLATIVE_TIMEZONE']
            tz_local = pytz.timezone(tz_name)

            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz_local)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(tz_local)
            query = query.filter(
                func.timezone(tz_name, func.timezone('UTC', Payment.created_on)).between(created_from, created_to))

        # Add ordering
        query = query.order_by(Payment.created_on.desc())

        if not return_all:
            # Add pagination
            pagination = query.paginate(per_page=limit, page=page)
            result, count = pagination.items, pagination.total
            # If maximum number of records is provided, return it as total
            if max_no_records > 0:
                count = max_no_records if max_no_records < count else count
        else:
            # If maximum number of records is provided, set the page with that number
            if max_no_records > 0:
                pagination = query.paginate(per_page=max_no_records, page=1)
                result, count = pagination.items, max_no_records
            else:
                result = query.all()
                count = len(result)

        return result, count

    @classmethod
    def find_payments_marked_for_delete(cls):
        """Return a Payment by id."""
        return cls.query.filter_by(payment_status_code=PaymentStatus.DELETE_ACCEPTED.value).all()


class PaymentSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors
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
