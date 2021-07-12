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

from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from pay_api.utils.enums import PaymentMethod

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
