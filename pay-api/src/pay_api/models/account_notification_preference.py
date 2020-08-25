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
from sqlalchemy import Boolean, ForeignKey

from .base_model import BaseModel
from .db import db, ma


class AccountNotificationPreference(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment Account."""

    __tablename__ = 'account_notification_preference'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    payment_account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True, index=True)

    # type of notifications
    type = db.Column(db.String(50), nullable=True)

    # when this is enabled , send out the  notifications
    enabled = db.Column('enabled', Boolean(), default=False)


class AccountNotificationPreferenceSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = AccountNotificationPreference
