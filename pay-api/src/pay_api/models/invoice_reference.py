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
"""Model to handle invoice references from third party systems."""
from __future__ import annotations
from datetime import datetime, timezone

from marshmallow import fields
from sqlalchemy import ForeignKey

from pay_api.utils.enums import InvoiceReferenceStatus

from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db


class InvoiceReference(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Invoice."""

    __tablename__ = 'invoice_references'
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
        'include_properties': [
            'id',
            'created_on',
            'invoice_id',
            'invoice_number',
            'is_consolidated',
            'reference_number',
            'status_code'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False, index=True)
    created_on = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(tz=timezone.utc))
    is_consolidated = db.Column(db.Boolean, nullable=False, default=False, index=True)

    invoice_number = db.Column(db.String(50), nullable=True, index=True)
    reference_number = db.Column(db.String(50), nullable=True)
    status_code = db.Column(db.String(20), ForeignKey(
        'invoice_reference_status_codes.code'), nullable=False, index=True)

    @classmethod
    def find_by_invoice_id_and_status(cls, invoice_id: int, status_code: str, exclude_consolidated=False) \
            -> InvoiceReference:
        """Return Invoice Reference by invoice id by status_code."""
        query = cls.query.filter_by(invoice_id=invoice_id).filter_by(status_code=status_code)
        if exclude_consolidated:
            query = query.filter(InvoiceReference.is_consolidated.is_(False))
        if status_code == InvoiceReferenceStatus.CANCELLED.value:
            return query.order_by(InvoiceReference.id.desc()).first()
        return query.one_or_none()

    @classmethod
    def find_any_active_reference_by_invoice_number(cls, invoice_number: str) -> InvoiceReference:
        """Return any active Invoice Reference by invoice number."""
        return cls.query.filter_by(invoice_number=invoice_number) \
            .filter_by(status_code=InvoiceReferenceStatus.ACTIVE.value).first()


class InvoiceReferenceSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the invoice reference."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = InvoiceReference

    status_code = fields.String(data_key='status_code')
