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

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from .audit import Audit
from .base_model import BaseModel
from .db import db, ma
from .payment_system import PaymentSystem
from .invoice import InvoiceSchema
from marshmallow import fields
from .base_schema import BaseSchema
from .invoice import Invoice


class Payment(db.Model, Audit, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment ."""

    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_system_code = db.Column(db.String(10), ForeignKey('payment_system.code'), nullable=False)
    payment_method_code = db.Column(db.String(10), ForeignKey('payment_method.code'), nullable=False)
    payment_status_code = db.Column(db.String(10), ForeignKey('status_code.code'), nullable=False)
    paid = db.Column(db.Float, nullable=True)

    payment_system = relationship(PaymentSystem, foreign_keys=[payment_system_code], lazy='select', innerjoin=True)
#    invoices = relationship(Invoice, lazy='select')
    invoices = relationship('Invoice')


    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Payment by id."""
        return cls.query.get(identifier)


class PaymentSchema(ma.ModelSchema, BaseSchema):
    """Main schema used to serialize the Payment."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Payment

    payment_system_code = fields.String(dump_to='payment_system')
    payment_method_code = fields.String(dump_to='payment_method')
    payment_status_code = fields.String(dump_to='status_code')

    invoices = ma.Nested(InvoiceSchema, many=True)

    _links = ma.Hyperlinks({
        'self': ma.URLFor('API.payments_payments', payment_id='<id>'),
        'collection': ma.URLFor('API.payments_payment'),
        'invoices': ma.URLFor('API.invoices_invoices', payment_id='<id>')
    })

