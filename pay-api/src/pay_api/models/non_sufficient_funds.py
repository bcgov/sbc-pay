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
from sqlalchemy import ForeignKey

from .base_model import BaseModel
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
            'cfs_account',
            'description',
            'invoice_id',
            'invoice_number'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cfs_account = db.Column(db.String(50), nullable=True, comment='CFS Account number')
    description = db.Column(db.String(50), nullable=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False, index=True, comment='CFS Invoice number')


@define
class NonSufficientFundsSchema:  # pylint: disable=too-few-public-methods
    """Used to search for NSF records."""

    id: int
    cfs_account: int
    invoice_id: int
    invoice_number: str
    description: str

    @classmethod
    def from_row(cls, row: NonSufficientFundsModel):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(id=row.id, cfs_account=row.cfs_account, description=row.description,
                   invoice_id=row.invoice_id, invoice_number=row.invoice_number)
