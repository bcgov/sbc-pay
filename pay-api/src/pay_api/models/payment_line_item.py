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

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db, ma


class PaymentLineItem(db.Model, BaseModel):
    """This class manages all of the base data about Payment Line Item."""

    __tablename__ = 'payment_line_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoice.id'), nullable=False)
    filing_fees = db.Column(db.Integer, nullable=False)
    fee_schedule_id = db.Column(db.Integer, ForeignKey('fee_schedule.fee_schedule_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=True)
    processing_fees = db.Column(db.Integer, nullable=True)
    service_fees = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(200), nullable=True)
    gst = db.Column(db.Integer, nullable=True)
    pst = db.Column(db.Integer, nullable=True)
    total = db.Column(db.Integer, nullable=False)

    @classmethod
    def find_by_id(cls, id: int):
        """Return a Line Item by id."""
        return cls.query.get(id)


class PaymentLineItemSchema(ma.ModelSchema):
    """Main schema used to serialize the Status Code."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentLineItem
