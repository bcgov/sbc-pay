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
"""Model to handle all operations related to Payment Account data."""
from __future__ import annotations

from attrs import define
from marshmallow import fields
from sqlalchemy import Boolean, ForeignKey
from sql_versioning import Versioned

from .base_model import BaseModel
from .db import db
from .base_schema import BaseSchema


class PaymentAccount(Versioned, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment Account."""

    __tablename__ = 'payment_accounts'
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
            'bcol_account',
            'bcol_user_id',
            'billable',
            'branch_name',
            'credit',
            'eft_enable',
            'name',
            'pad_activation_date',
            'pad_tos_accepted_by',
            'pad_tos_accepted_date',
            'payment_method',
            'statement_notification_enabled'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Account ID from auth, not present for FAS accounts.
    auth_account_id = db.Column(db.String(50), nullable=True, index=True)

    # used for sending out notifications.The statement emails needs account name
    name = db.Column(db.String(250), nullable=True, index=False)
    branch_name = db.Column(db.String(250), nullable=True, index=False)

    payment_method = db.Column(db.String(15), ForeignKey('payment_methods.code'), nullable=True)

    bcol_user_id = db.Column(db.String(50), nullable=True, index=True)
    bcol_account = db.Column(db.String(50), nullable=True, index=True)

    # when this is enabled , send out the  notifications
    statement_notification_enabled = db.Column('statement_notification_enabled', Boolean(), default=False)

    credit = db.Column(db.Numeric(19, 2), nullable=True)
    billable = db.Column(Boolean(), default=True)
    eft_enable = db.Column(Boolean(), nullable=False, default=False)

    # before this date , the account shouldn't get used
    pad_activation_date = db.Column(db.DateTime, nullable=True)
    pad_tos_accepted_date = db.Column(db.DateTime, nullable=True)
    pad_tos_accepted_by = db.Column(db.String(50), nullable=True)

    def __str__(self):
        """Override to string."""
        return f'{self.name or ""} ({self.auth_account_id})'

    @classmethod
    def find_by_auth_account_id(cls, auth_account_id: str) -> PaymentAccount | None:
        """Return a Account by id."""
        return cls.query.filter_by(auth_account_id=str(auth_account_id)).one_or_none()


class PaymentAccountSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment Account."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentAccount
        exclude = ['pad_activation_date']

    credit = fields.Float(data_key='credit')
    payment_method = fields.String(data_key='payment_method')
    auth_account_id = fields.String(data_key='account_id')
    name = fields.String(data_key='account_name')
    branch_name = fields.String(data_key='branch_name')


@define
class PaymentAccountSearchModel:  # pylint: disable=too-few-public-methods
    """Payment Account Search model."""

    account_name: str
    billable: bool
    account_id: str
    branch_name: str

    @classmethod
    def from_row(cls, row: PaymentAccount):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(account_name=row.name, billable=row.billable, account_id=row.auth_account_id,
                   branch_name=row.branch_name)
