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
"""Model to handle EFT short name to BCROS account mapping links."""
from datetime import datetime
from _decimal import Decimal
from attrs import define


from sql_versioning import Versioned
from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EFTShortnameLinks(Versioned, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the EFT short name links to auth account mapping."""

    __tablename__ = 'eft_short_name_links'
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
            'auth_account_id',
            'created_on',
            'eft_short_name_id',
            'status_code',
            'updated_by',
            'updated_by_name',
            'updated_on'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    eft_short_name_id = db.Column(db.Integer, ForeignKey('eft_short_names.id'), nullable=False, index=True)
    auth_account_id = db.Column('auth_account_id', db.String(50), nullable=False, index=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now)
    status_code = db.Column('status_code', db.String(25), nullable=False, index=True)
    updated_by = db.Column('updated_by', db.String(100), nullable=True)
    updated_by_name = db.Column('updated_by_name', db.String(100), nullable=True)
    updated_on = db.Column('updated_on', db.DateTime, nullable=True)

    @classmethod
    def find_by_short_name_id(cls, short_name_id: id):
        """Find by eft short name."""
        return cls.query.filter_by(eft_short_name_id=short_name_id).all()


@define
class EFTShortnameLinkSchema:  # pylint: disable=too-few-public-methods
    """Main schema used to serialize the EFT Short name link."""

    id: int
    short_name_id: str
    status_code: str
    account_id: str
    account_name: str
    account_branch: str
    statement_id: str
    amount_owing: Decimal
    updated_by: str
    updated_by_name: str
    updated_on: datetime

    @classmethod
    def from_row(cls, row: EFTShortnameLinks):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(id=row.id,
                   short_name_id=row.eft_short_name_id,
                   status_code=row.status_code,
                   account_id=row.auth_account_id,
                   account_name=getattr(row, 'account_name', None),
                   account_branch=getattr(row, 'account_branch', None),
                   statement_id=getattr(row, 'latest_statement_id', None),
                   amount_owing=getattr(row, 'total_owing', None),
                   updated_by=row.updated_by,
                   updated_by_name=row.updated_by_name,
                   updated_on=row.updated_on
                   )
