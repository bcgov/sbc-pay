# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service class to control all the operations related to statements."""
from datetime import date, datetime
from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.models import StatementRecipients as StatementRecipientsModel
from pay_api.models import StatementRecipientsSchema as NotificationSchema
from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel


class StatementRecipients:
    """Service to manage statement related operations."""

    def __init__(self):
        """Return a Statement Service Object."""
        self.__dao = None
        self._id: int = None
        self._auth_user_id = None
        self._firstname = None
        self._lastname = None
        self._email = None
        self._payment_account_id = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = StatementRecipientsModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.auth_user_id: str = self._dao.auth_user_id
        self.firstname: int = self._dao.firstname
        self.lastname: datetime = self._dao.lastname
        self.email: datetime = self._dao.email
        self.payment_account_id: int = self._dao.payment_account_id

    @property
    def auth_user_id(self):
        """Return the auth_user_id for the statement settings."""
        return self._auth_user_id

    @auth_user_id.setter
    def auth_user_id(self, value: int):
        """Set the auth_user_id for the statement settings."""
        self._auth_user_id = value
        self._dao.auth_user_id = value

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def firstname(self):
        """Return the firstname of the statement setting."""
        return self._firstname

    @firstname.setter
    def firstname(self, value: date):
        """Set the firstname for the statement setting."""
        self._firstname = value
        self._dao.firstname = value

    @property
    def payment_account_id(self):
        """Return the account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: str):
        """Set the account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def lastname(self):
        """Return the lastname of the statement setting."""
        return self._lastname

    @lastname.setter
    def lastname(self, value: date):
        """Set the lastname for the statement setting."""
        self._lastname = value
        self._dao.lastname = value

    @property
    def email(self):
        """Return the lastname of the statement setting."""
        return self._lastname

    @email.setter
    def email(self, value: date):
        """Set the email for the statement setting."""
        self._email = value
        self._dao.email = value

    def asdict(self):
        """Return the invoice as a python dict."""
        statements_notification_recipients_schema = NotificationSchema()
        d = statements_notification_recipients_schema.dump(self._dao)
        return d

    @staticmethod
    def find_statement_notification_details(auth_account_id: str):
        """Find statements by account id."""
        current_app.logger.debug(f'<find_statement_notification_details {auth_account_id}')
        recipients = StatementRecipientsModel.find_all_recipients(auth_account_id)
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        data = {
            'recipients': NotificationSchema().dump(recipients, many=True),
            'statement_notification_enabled': getattr(payment_account, 'statement_notification_enabled', False)
        }

        current_app.logger.debug('>find_statement_notification_details')
        return data

    @staticmethod
    def update_statement_notification_details(auth_account_id: str, notification_details: Tuple[Dict[str, Any]]):
        """Update statements notification settings by account id.

        Update the payment Account.
        Update the recepients
        """
        payment_account = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        if payment_account is None:
            payment_account = PaymentAccountModel()
            payment_account.auth_account_id = auth_account_id
        payment_account.name = notification_details.get('accountName')
        payment_account.statement_notification_enabled = notification_details.get('statementNotificationEnabled')
        payment_account.save()
        recepient_list: list = []

        # if no object is passed , dont update anything.Empty list passed means , delete everything
        if (recepients := notification_details.get('recipients')) is not None:
            StatementRecipientsModel.delete_all_recipients(payment_account.id)
            for rec in recepients or []:
                recipient = StatementRecipientsModel()
                recipient.auth_user_id = rec.get('authUserId')
                recipient.firstname = rec.get('firstname')
                recipient.lastname = rec.get('lastname')
                recipient.email = rec.get('email')
                recipient.payment_account_id = payment_account.id
                recepient_list.append(recipient)
            StatementRecipientsModel.bulk_save_recipients(recepient_list)
