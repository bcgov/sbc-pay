# Copyright © 2024 Province of British Columbia
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

    __tablename__ = "receipts"
    # this mapper is used so that new and old versions of the service can be run simultaneously,
    # making rolling upgrades easier
    # This is used by SQLAlchemy to explicitly define which fields we're interested
    # so it doesn't freak out and say it can't map the structure if other fields are present.
    # This could occur from a failed deploy or during an upgrade.
    # The other option is to tell SQLAlchemy to ignore differences, but that is ambiguous
    # and can interfere with Alembic upgrades.
    #
    # NOTE: please keep mapper names in alpha-order, easier to track that way
    #       Exception, id is always first, _fields first
    __mapper_args__ = {
        "include_properties": [
            "id",
            "invoice_id",
            "receipt_amount",
            "receipt_date",
            "receipt_number",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey("invoices.id"), nullable=False, index=True)
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

    @classmethod
    def find_all_receipts_for_invoice(cls, invoice_id: int):
        """Return all Receipts for invoice id."""
        return cls.query.filter_by(invoice_id=invoice_id).all()


class ReceiptSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Receipt."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Receipt
        load_instance = True

    receipt_date = fields.DateTime(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
