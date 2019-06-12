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

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from .audit import Audit
from .base_model import BaseModel
from .db import db, ma
from .payment_line_item import PaymentLineItem  # pylint: disable=unused-import


class Invoice(db.Model, Audit, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Invoice."""

    __tablename__ = 'invoice'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.Integer, ForeignKey('payment.id'), nullable=False)

    invoice_number = db.Column(db.String(50), nullable=True)
    reference_number = db.Column(db.String(50), nullable=True)
    invoice_status_code = db.Column(db.String(10), ForeignKey('status_code.code'), nullable=False)
    account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Float, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    refund = db.Column(db.Float, nullable=True)

    payment_line_items = relationship('PaymentLineItem')

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Invoice by id."""
        return cls.query.get(identifier)

    @classmethod
    def find_by_payment_id(cls, identifier: int):
        """Return a Invoice by id."""
        return cls.query.filter_by(payment_id=identifier).one_or_none()


class InvoiceSchema(ma.ModelSchema):
    """Main schema used to serialize the Status Code."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Invoice
