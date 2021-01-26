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
"""Model to handle all operations related to Receipt."""

import pytz
from marshmallow import fields
from sqlalchemy import ForeignKey

from pay_api.utils.constants import LEGISLATIVE_TIMEZONE
from .base_model import BaseModel
from .db import db, ma


class Receipt(BaseModel):
    """This class manages all of the base data about Receipt."""

    __tablename__ = 'receipts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False)
    receipt_number = db.Column(db.String(50), nullable=False)
    receipt_date = db.Column(db.DateTime)
    receipt_amount = db.Column(db.Float)

    @classmethod
    def find_by_invoice_id_and_receipt_number(cls, invoice_id: int, receipt_number: str = None):
        """Return a Receipt by invoice id and receipt_number."""
        query = cls.query.filter_by(invoice_id=invoice_id)
        if receipt_number:
            query.filter_by(receipt_number=receipt_number)
        return query.one_or_none()


class ReceiptSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Receipt."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Receipt

    receipt_date = fields.DateTime(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
