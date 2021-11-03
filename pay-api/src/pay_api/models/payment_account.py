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
"""Model to handle all operations related to Payment Account data."""

from marshmallow import fields
from sqlalchemy import Boolean, ForeignKey

from .base_model import VersionedModel
from .db import db
from .base_schema import BaseSchema


class PaymentAccount(VersionedModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment Account."""

    __tablename__ = 'payment_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Account ID from auth, not present for FAS accounts.
    auth_account_id = db.Column(db.String(50), nullable=True, index=True)

    # used for sending out notifications.The statement emails needs account name
    name = db.Column(db.String(250), nullable=True, index=False)

    payment_method = db.Column(db.String(15), ForeignKey('payment_methods.code'), nullable=True)

    bcol_user_id = db.Column(db.String(50), nullable=True, index=True)
    bcol_account = db.Column(db.String(50), nullable=True, index=True)

    # when this is enabled , send out the  notifications
    statement_notification_enabled = db.Column('statement_notification_enabled', Boolean(), default=False)

    credit = db.Column(db.Float, nullable=True)
    billable = db.Column(Boolean(), default=True)

    # before this date , the account shouldn't get used
    pad_activation_date = db.Column(db.DateTime, nullable=True)
    pad_tos_accepted_date = db.Column(db.DateTime, nullable=True)
    pad_tos_accepted_by = db.Column(db.String(50), nullable=True)

    def __str__(self):
        """Override to string."""
        return f'{self.name or ""} ({self.auth_account_id})'

    @classmethod
    def find_by_auth_account_id(cls, auth_account_id: str):
        """Return a Account by id."""
        return cls.query.filter_by(auth_account_id=str(auth_account_id)).one_or_none()


class PaymentAccountSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment Account."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentAccount
        exclude = ['versions', 'pad_activation_date']

    payment_method = fields.String(data_key='payment_method')
    auth_account_id = fields.String(data_key='account_id')
    name = fields.String(data_key='account_name')
