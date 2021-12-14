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
from typing import Dict, List

import pytz
from flask import current_app
from marshmallow import fields
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import relationship

from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import PaymentMethod, RoutingSlipStatus
from pay_api.utils.util import get_str_by_path

from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice import Invoice, InvoiceSchema
from .payment import Payment, PaymentSchema
from .payment_account import PaymentAccount, PaymentAccountSchema
from .refund import Refund, RefundSchema


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
    parent_number = db.Column(db.String(), ForeignKey('routing_slips.number'), nullable=True)
    refund_amount = db.Column(db.Numeric(), nullable=True, default=0)

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
                                        f"['{PaymentMethod.INTERNAL.value}']))",
                            viewonly=True,
                            lazy='joined'
                            )

    refunds = relationship(Refund, viewonly=True,
                           primaryjoin=f'and_(RoutingSlip.id == Refund.routing_slip_id,'
                                       f'RoutingSlip.status.in_('
                                       f'[f"{RoutingSlipStatus.REFUND_REQUESTED.value}",'
                                       f'f"{RoutingSlipStatus.REFUND_AUTHORIZED.value}"]))',
                           lazy='joined')

    parent = relationship('RoutingSlip', remote_side=[number], lazy='select')

    @classmethod
    def find_by_number(cls, number: str) -> RoutingSlip:
        """Return a routing slip by number."""
        return cls.query.filter_by(number=number).one_or_none()

    @classmethod
    def find_children(cls, number: str) -> List[RoutingSlip]:
        """Return children for the routing slip."""
        return cls.query.filter_by(parent_number=number).all()

    @classmethod
    def find_by_payment_account_id(cls, payment_account_id: str) -> RoutingSlip:
        """Return a routing slip by payment account number."""
        return cls.query.filter_by(payment_account_id=payment_account_id).one_or_none()

    @classmethod
    def find_all_by_payment_account_id(cls, payment_account_id: str) -> List[RoutingSlip]:
        """Return a routing slip by payment account number."""
        return cls.query.filter_by(payment_account_id=payment_account_id).all()

    @classmethod
    def search(cls, search_filter: Dict,  # pylint: disable=too-many-arguments
               page: int, limit: int, return_all: bool, max_no_records: int = 0) -> (List[RoutingSlip], int):
        """Search for routing slips by the criteria provided."""
        query = db.session.query(RoutingSlip)

        if rs_number := search_filter.get('routingSlipNumber', None):
            query = query.filter(RoutingSlip.number.ilike('%' + rs_number + '%'))

        if status := search_filter.get('status', None):
            query = query.filter(RoutingSlip.status == status)

        if total_amount := search_filter.get('totalAmount', None):
            query = query.filter(RoutingSlip.total == total_amount)

        query = cls._add_date_filter(query, search_filter)

        query = query.join(PaymentAccount)
        if initiator := search_filter.get('initiator', None):
            query = query.filter(RoutingSlip.created_name.ilike('%' + initiator + '%'))

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

        if end_date := get_str_by_path(search_filter, 'dateFilter/endDate'):
            created_to = datetime.strptime(end_date, DT_SHORT_FORMAT)
        if start_date := get_str_by_path(search_filter, 'dateFilter/startDate'):
            created_from = datetime.strptime(start_date, DT_SHORT_FORMAT)
        # if passed in details
        if created_to and created_from:
            # Truncate time for from date and add max time for to date
            tz_name = current_app.config['LEGISLATIVE_TIMEZONE']
            tz_local = pytz.timezone(tz_name)

            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz_local)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(tz_local)

            # If the dateFilter/target is provided then filter on that column, else filter on routing_slip_date
            target_date = getattr(RoutingSlip,
                                  get_str_by_path(search_filter, 'dateFilter/target') or 'routing_slip_date')

            query = query.filter(
                func.timezone(tz_name, func.timezone('UTC', target_date))
                    .between(created_from, created_to))
        return query

    @classmethod
    def _add_receipt_number(cls, query, search_filter):
        conditions = []
        if receipt_number := search_filter.get('receiptNumber', None):
            conditions.append(
                and_(Payment.payment_account_id == PaymentAccount.id,
                     and_(Payment.cheque_receipt_number == receipt_number,
                          Payment.payment_method_code == PaymentMethod.CASH.value)))
        if cheque_receipt_number := search_filter.get('chequeReceiptNumber', None):
            conditions.append(
                and_(Payment.payment_account_id == PaymentAccount.id,
                     and_(Payment.cheque_receipt_number == cheque_receipt_number,
                          Payment.payment_method_code == PaymentMethod.CHEQUE.value)))
        if conditions:
            query = query.join(Payment).filter(*conditions)
        return query

    @classmethod
    def _add_folio_filter(cls, query, search_filter):
        if folio_number := search_filter.get('folioNumber', None):
            query = query.join(Invoice).filter(
                and_(Invoice.routing_slip == RoutingSlip.number, and_(Invoice.folio_number == folio_number,
                                                                      Invoice.payment_method_code.in_(
                                                                          [PaymentMethod.INTERNAL.value]))))
        return query


class RoutingSlipSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors, too-few-public-methods
    """Main schema used to serialize the Routing Slip."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = RoutingSlip
        exclude = ['parent']

    total = fields.Float(data_key='total')
    remaining_amount = fields.Float(data_key='remaining_amount')
    # pylint: disable=no-member
    payments = ma.Nested(PaymentSchema, many=True, data_key='payments')
    payment_account = ma.Nested(PaymentAccountSchema, many=False, data_key='payment_account')
    refunds = ma.Nested(RefundSchema, many=True, data_key='refunds')
    invoices = ma.Nested(InvoiceSchema, many=True, data_key='invoices', exclude=['_links'])
    status = fields.String(data_key='status')
    parent_number = fields.String(data_key='parent_number')
