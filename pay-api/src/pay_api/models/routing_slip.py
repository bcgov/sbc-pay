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
"""Model to handle all operations related to Routing Slip."""
from __future__ import annotations

from datetime import datetime
from operator import and_
from typing import Dict

import pytz
from flask import current_app
from marshmallow import fields
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import relationship

from pay_api.utils.enums import PaymentMethod
from pay_api.utils.util import get_first_and_last_dates_of_month, get_str_by_path, get_week_start_and_end_date

from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice import Invoice, InvoiceSchema
from .payment import Payment, PaymentSchema
from .payment_account import PaymentAccount, PaymentAccountSchema


class RoutingSlip(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Routing Slip."""

    __tablename__ = 'routing_slips'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.String(), unique=True)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True)
    status = db.Column(db.String(), ForeignKey('routing_slip_status_codes.code'), nullable=True)
    total = db.Column(db.Numeric(), nullable=True, default=0)
    remaining_amount = db.Column(db.Numeric(), nullable=True, default=0)
    routing_slip_date = db.Column(db.Date, nullable=False)

    payment_account = relationship(PaymentAccount, foreign_keys=[payment_account_id], lazy='select', innerjoin=True)
    payments = relationship(Payment,
                            secondary='join(PaymentAccount, Payment, PaymentAccount.id == Payment.payment_account_id)',
                            primaryjoin='and_(RoutingSlip.payment_account_id == PaymentAccount.id)',
                            viewonly=True,
                            lazy='joined'
                            )

    invoices = relationship(Invoice,
                            primaryjoin='and_(RoutingSlip.number == foreign(Invoice.routing_slip), '
                                        f'Invoice.payment_method_code.in_('
                                        f"['{PaymentMethod.CASH.value}','{PaymentMethod.CHEQUE.value}']))",
                            viewonly=True,
                            lazy='joined'
                            )

    @classmethod
    def find_by_number(cls, number: str) -> RoutingSlip:
        """Return a routing slip by number."""
        return cls.query.filter_by(number=number).one_or_none()

    @classmethod
    def search(cls, search_filter: Dict,    # pylint: disable=too-many-arguments
               page: int, limit: int, return_all: bool, max_no_records: int = 0):
        """Search for routing slips by the criteria provided."""
        query = db.session.query(RoutingSlip)

        if rs_number := search_filter.get('routingSlipNumber', None):
            query = query.filter(RoutingSlip.number == rs_number)
        if status := search_filter.get('status', None):
            query = query.filter(RoutingSlip.status == status)

        if total_amount := search_filter.get('totalAmount', None):
            query = query.filter(RoutingSlip.total == total_amount)

        query = cls._add_date_filter(query, search_filter)

        query = query.join(PaymentAccount)
        if initiator := search_filter.get('initiator', None):
            query = query.filter(PaymentAccount.name.ilike('%' + initiator + '%'))

        query = cls._add_receipt_number(query, search_filter)

        query = cls._add_folio_filter(query, search_filter)

        # Add ordering
        query = query.order_by(RoutingSlip.created_on.desc())

        if not return_all:
            pagination = query.paginate(per_page=limit, page=page)
            result, count = pagination.items, pagination.total
            if max_no_records > 0:
                count = max_no_records if max_no_records < count else count
        else:
            if max_no_records > 0:
                pagination = query.paginate(per_page=max_no_records, page=1)
                result, count = pagination.items, max_no_records
            else:
                result = query.all()
                count = len(result)

        return result, count

    @classmethod
    def _add_date_filter(cls, query, search_filter):
        # Find start and end dates for folio search
        created_from: datetime = None
        created_to: datetime = None
        if get_str_by_path(search_filter, 'dateFilter/endDate'):
            created_to = datetime.strptime(get_str_by_path(search_filter, 'dateFilter/endDate'), '%m/%d/%Y')
        if get_str_by_path(search_filter, 'dateFilter/startDate'):
            created_from = datetime.strptime(get_str_by_path(search_filter, 'dateFilter/startDate'), '%m/%d/%Y')
        if get_str_by_path(search_filter, 'weekFilter/index'):
            created_from, created_to = get_week_start_and_end_date(
                int(get_str_by_path(search_filter, 'weekFilter/index')))
        if get_str_by_path(search_filter, 'monthFilter/month') and get_str_by_path(search_filter,
                                                                                   'monthFilter/year'):
            # find month
            month = int(get_str_by_path(search_filter, 'monthFilter/month'))
            year = int(get_str_by_path(search_filter, 'monthFilter/year'))
            created_from, created_to = get_first_and_last_dates_of_month(month=month, year=year)
        # if passed in details
        if created_to and created_from:
            # Truncate time for from date and add max time for to date
            tz_name = current_app.config['LEGISLATIVE_TIMEZONE']
            tz_local = pytz.timezone(tz_name)

            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz_local)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(tz_local)
            query = query.filter(
                func.timezone(tz_name, func.timezone('UTC', RoutingSlip.created_on)).between(created_from, created_to))
        return query

    @classmethod
    def _add_receipt_number(cls, query, search_filter):
        if receipt_number := search_filter.get('receiptNumber', None):
            query = query.join(Payment).filter(
                and_(Payment.payment_account_id == PaymentAccount.id, Payment.receipt_number == receipt_number))
        return query

    @classmethod
    def _add_folio_filter(cls, query, search_filter):
        if folio_number := search_filter.get('folioNumber', None):
            query = query.join(Invoice).filter(
                and_(Invoice.routing_slip == RoutingSlip.number, and_(Invoice.folio_number == folio_number,
                                                                      Invoice.payment_method_code.in_(
                                                                          [PaymentMethod.CASH.value,
                                                                           PaymentMethod.CHEQUE.value]))))
        return query


class RoutingSlipSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors, too-few-public-methods
    """Main schema used to serialize the Routing Slip."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = RoutingSlip

    total = fields.Float(data_key='total')
    remaining_amount = fields.Float(data_key='remaining_amount')
    # pylint: disable=no-member
    payments = ma.Nested(PaymentSchema, many=True, data_key='payments')
    payment_account = ma.Nested(PaymentAccountSchema, many=False, data_key='payment_account')
    invoices = ma.Nested(InvoiceSchema, many=True, data_key='invoices', exclude=['_links'])
    status = fields.String(data_key='status')
