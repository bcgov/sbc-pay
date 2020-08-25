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
"""Model to handle all operations related to Notification Recipients."""
from sqlalchemy import String, ForeignKey

from .base_model import BaseModel
from .db import db, ma


class NotificationRecipients(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Notification Recipients."""

    __tablename__ = 'notification_recipients'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    auth_user_id = db.Column(db.Integer, nullable=True, index=True)
    firstname = db.Column('first_name', String(200))
    lastname = db.Column('last_name', String(200))
    email = db.Column('email', String(200))
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True, index=True)
    # incase if more notification prefernce comes
    notification_preference_id = db.Column(db.Integer, ForeignKey('account_notification_preference.id'), nullable=True, index=True)


class NotificationRecipientsSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = NotificationRecipients
