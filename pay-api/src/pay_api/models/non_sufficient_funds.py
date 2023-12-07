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
"""Model to handle all operations related to Non-Sufficient Funds."""
from __future__ import annotations

from attrs import define
from marshmallow import fields
from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db


class NonSufficientFundsModel(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Non-Sufficient Funds."""

    __tablename__ = 'non_sufficient_funds'
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
            'description',
            'invoice_id',
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.String(50), nullable=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False)


class NonSufficientFundsSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Non-Sufficient Funds."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = NonSufficientFundsModel

    description = fields.String(data_key='description')
    invoice_id = fields.Integer(data_key='invoice_id')


@define
class NonSufficientFundsSearchModel: # pylint: disable=too-few-public-methods
    """Used to search for NSF records."""

    id: int
    invoice_id: int
    description: str

    @classmethod
    def from_row(cls, row: NonSufficientFundsModel):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(invoice_id=row.invoice_id, description=row.description)
