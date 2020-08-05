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
"""Model to handle all operations related to Payment Line Item."""

from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from .base_model import BaseModel
from .db import db, ma
from .fee_schedule import FeeSchedule


class PaymentLineItem(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment Line Item."""

    __tablename__ = 'payment_line_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoice.id'), nullable=False)
    filing_fees = db.Column(db.Float, nullable=False)
    fee_schedule_id = db.Column(db.Integer, ForeignKey('fee_schedule.fee_schedule_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=True)
    priority_fees = db.Column(db.Float, nullable=True)
    future_effective_fees = db.Column(db.Float, nullable=True)
    description = db.Column(db.String(200), nullable=True)
    gst = db.Column(db.Float, nullable=True)
    pst = db.Column(db.Float, nullable=True)
    total = db.Column(db.Float, nullable=False)
    line_item_status_code = db.Column(db.String(20), ForeignKey('line_item_status_code.code'), nullable=False)
    waived_fees = db.Column(db.Float, nullable=True)
    waived_by = db.Column(db.String(50), nullable=True, default=None)
    service_fees = db.Column(db.Float, nullable=True)

    fee_distribution_id = db.Column(db.Integer, ForeignKey('distribution_code.distribution_code_id'), nullable=False)

    fee_schedule = relationship(FeeSchedule, foreign_keys=[fee_schedule_id], lazy='joined', innerjoin=True)

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Line Item by id."""
        return cls.query.get(identifier)

    @classmethod
    def find_by_invoice_ids(cls, invoice_ids: list):
        """Return list of line items by list of invoice ids."""
        return db.session.query(PaymentLineItem).filter(PaymentLineItem.invoice_id.in_(invoice_ids)).order_by(
            PaymentLineItem.invoice_id.desc()).all()


class PaymentLineItemSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment line item."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentLineItem
        exclude = ['fee_schedule_id', 'fee_schedule']

    line_item_status_code = fields.String(data_key='status_code')
