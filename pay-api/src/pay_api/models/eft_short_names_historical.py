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
"""Model to handle all operations related to EFT Short name historical audit data."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Self

from attr import define
from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EFTShortnamesHistorical(BaseModel):  # pylint:disable=too-many-instance-attributes
    """This class manages all EFT Short name historical data."""

    __tablename__ = 'eft_short_names_historical'
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
            'amount',
            'created_by',
            'created_on',
            'credit_balance',
            'description',
            'hidden',
            'invoice_id',
            'is_processing',
            'payment_account_id',
            'related_group_link_id',
            'short_name_id',
            'statement_number',
            'transaction_date',
            'transaction_type'
        ]
    }
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    amount = db.Column(db.Numeric(19, 2), nullable=False)
    created_by = db.Column(db.String, nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    credit_balance = db.Column(db.Numeric(19, 2), nullable=False)
    hidden = db.Column(db.Boolean(), nullable=False, default=False, index=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=True, index=True)
    is_processing = db.Column(db.Boolean(), nullable=False, default=False)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)
    related_group_link_id = db.Column(db.Integer, nullable=True, index=True)
    short_name_id = db.Column(db.Integer, ForeignKey('eft_short_names.id'), nullable=False)
    statement_number = db.Column(db.Integer, nullable=True)
    transaction_date = db.Column(db.DateTime, nullable=False, index=True)
    transaction_type = db.Column(db.String, nullable=False)

    @classmethod
    def find_by_related_group_link_id(cls, group_link_id: int) -> Self:
        """Find historical records by related EFT Credit Invoice Link group id."""
        return cls.query.filter_by(related_group_link_id=group_link_id).one_or_none()


@define
class EFTShortnameHistorySchema:  # pylint: disable=too-few-public-methods
    """Main schema used to serialize an EFT Short name historical record."""

    historical_id: int
    account_id: str
    account_name: str
    account_branch: str
    amount: Decimal
    invoice_id: int
    statement_number: int
    short_name_id: int
    short_name_balance: Decimal
    transaction_date: datetime
    transaction_type: str
    is_processing: bool
    is_reversible: bool

    @classmethod
    def from_row(cls, row):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(historical_id=row.id,
                   short_name_id=row.short_name_id,
                   amount=getattr(row, 'amount', None),
                   short_name_balance=getattr(row, 'credit_balance', None),
                   account_id=getattr(row, 'auth_account_id', None),
                   account_name=getattr(row, 'account_name', None),
                   account_branch=getattr(row, 'account_branch', None),
                   invoice_id=getattr(row, 'invoice_id', None),
                   statement_number=getattr(row, 'statement_number', None),
                   transaction_date=getattr(row, 'transaction_date', None),
                   transaction_type=getattr(row, 'transaction_type', None),
                   is_processing=bool(getattr(row, 'is_processing', False)),
                   is_reversible=bool(getattr(row, 'is_reversible', False)))
