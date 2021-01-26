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
"""Model to handle all operations related to invoice refund."""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db, ma


class Refund(BaseModel):
    """This class manages all of the base data about Invoice Refund."""

    __tablename__ = 'refunds'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False)
    requested_date = db.Column(db.DateTime)
    reason = db.Column(db.String(250))
    requested_by = db.Column(db.String(50))

    @classmethod
    def find_by_invoice_id(cls, invoice_id: int):
        """Return a refund by invoice id."""
        return cls.query.filter_by(invoice_id=invoice_id).one_or_none()


class RefundSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Refund."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Refund
