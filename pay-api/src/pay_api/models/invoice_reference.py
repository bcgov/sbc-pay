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
"""Model to handle invoice references from third party systems."""

from marshmallow import fields
from sqlalchemy import ForeignKey

from pay_api.utils.enums import InvoiceReferenceStatus

from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db


class InvoiceReference(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Invoice."""

    __tablename__ = 'invoice_references'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False, index=True)

    invoice_number = db.Column(db.String(50), nullable=True, index=True)
    reference_number = db.Column(db.String(50), nullable=True)
    status_code = db.Column(db.String(20), ForeignKey(
        'invoice_reference_status_codes.code'), nullable=False, index=True)

    @classmethod
    def find_by_invoice_id_and_status(cls, invoice_id: int, status_code: str):
        """Return active Invoice Reference by invoice id."""
        return cls.query.filter_by(invoice_id=invoice_id).filter_by(status_code=status_code).one_or_none()

    @classmethod
    def find_any_active_reference_by_invoice_number(cls, invoice_number: str):
        """Return any active Invoice Reference by invoice number."""
        return cls.query.filter_by(invoice_number=invoice_number) \
            .filter_by(status_code=InvoiceReferenceStatus.ACTIVE.value).first()


class InvoiceReferenceSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the invoice reference."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = InvoiceReference

    status_code = fields.String(data_key='status_code')
