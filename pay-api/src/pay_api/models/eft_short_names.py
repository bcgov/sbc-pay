# Copyright © 2023 Province of British Columbia
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
"""Model to handle EFT TDI17 short name to BCROS account mapping."""
from datetime import datetime, timezone
from _decimal import Decimal
from attrs import define


from sql_versioning import Versioned

from .base_model import BaseModel
from .db import db


class EFTShortnames(Versioned, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the EFT short names."""

    __tablename__ = 'eft_short_names'
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
            'cas_supplier_number',
            'created_on',
            'email',
            'short_name'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    short_name = db.Column('short_name', db.String, nullable=False, index=True)
    email = db.Column(db.String(100), nullable=True)
    cas_supplier_number = db.Column(db.String(), nullable=True)

    @classmethod
    def find_by_short_name(cls, short_name: str):
        """Find by eft short name."""
        return cls.query.filter_by(short_name=short_name).one_or_none()


@define
class EFTShortnameSchema:  # pylint: disable=too-few-public-methods
    """Main schema used to serialize the EFT Short name."""

    id: int
    account_id: str
    account_name: str
    account_branch: str
    amount_owing: Decimal
    created_on: datetime
    email: str
    cas_supplier_number: str
    short_name: str
    statement_id: int
    status_code: str
    cfs_account_status: str

    @classmethod
    def from_row(cls, row: EFTShortnames):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(id=row.id,
                   account_id=getattr(row, 'auth_account_id', None),
                   account_name=getattr(row, 'account_name', None),
                   account_branch=getattr(row, 'account_branch', None),
                   amount_owing=getattr(row, 'total_owing', None),
                   created_on=row.created_on,
                   short_name=row.short_name,
                   email=getattr(row, 'email'),
                   cas_supplier_number=getattr(row, 'cas_supplier_number'),
                   statement_id=getattr(row, 'latest_statement_id', None),
                   status_code=getattr(row, 'status_code', None),
                   cfs_account_status=getattr(row, 'cfs_account_status', None)
                   )


@define
class EFTShortnameSummarySchema:
    """Main schema used to serialize the EFT Short name summaries."""

    id: int
    short_name: str
    last_payment_received_date: datetime
    credits_remaining: Decimal
    linked_accounts_count: int

    @classmethod
    def from_row(cls, row: EFTShortnames):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(id=row.id,
                   short_name=row.short_name,
                   last_payment_received_date=getattr(row, 'last_payment_received_date', None),
                   credits_remaining=getattr(row, 'credits_remaining', None),
                   linked_accounts_count=getattr(row, 'linked_accounts_count', None)
                   )
