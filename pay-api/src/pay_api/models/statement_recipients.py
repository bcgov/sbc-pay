# Copyright © 2022 Province of British Columbia
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

from sqlalchemy import ForeignKey, String

from .base_model import BaseModel
from .db import db, ma
from .payment_account import PaymentAccount


class StatementRecipients(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Notification Recipients."""

    __tablename__ = 'statement_recipients'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    auth_user_id = db.Column(db.Integer, nullable=True, index=True)
    firstname = db.Column('first_name', String(200))
    lastname = db.Column('last_name', String(200))
    email = db.Column('email', String(200))
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)

    @classmethod
    def find_all_recipients(cls, auth_account_id: str):
        """Return all active recipients for an account."""
        return cls.query \
            .join(PaymentAccount) \
            .filter(PaymentAccount.auth_account_id == auth_account_id).all()

    @classmethod
    def find_all_recipients_for_payment_id(cls, payment_account_id: str):
        """Return all active recipients for an account."""
        return cls.query \
            .filter(StatementRecipients.payment_account_id == payment_account_id).all()

    @classmethod
    def delete_all_recipients(cls, payment_account_id: str):
        """Return all active recipients for an account."""
        db.session.query(StatementRecipients).filter(
            StatementRecipients.payment_account_id == payment_account_id).delete()

    @classmethod
    def bulk_save_recipients(cls, recipients: list):
        """Bulk save Recipients."""
        db.session.bulk_save_objects(recipients)
        BaseModel.commit()


class StatementRecipientsSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = StatementRecipients
