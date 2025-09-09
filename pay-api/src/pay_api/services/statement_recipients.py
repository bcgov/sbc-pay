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
from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.models import StatementRecipients as StatementRecipientsModel
from pay_api.models import StatementRecipientsSchema as NotificationSchema
from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel
from pay_api.services.activity_log_publisher import ActivityLogPublisher
from pay_api.utils.dataclasses import StatementRecipientChange
from pay_api.utils.enums import QueueSources


class StatementRecipients:
    """Service to manage statement related operations."""

    @staticmethod
    def find_statement_notification_details(auth_account_id: str):
        """Find statements by account id."""
        current_app.logger.debug(f"<find_statement_notification_details {auth_account_id}")
        recipients = StatementRecipientsModel.find_all_recipients(auth_account_id)
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        # Future use CATTRS
        data = {
            "recipients": NotificationSchema().dump(recipients, many=True),
            "statement_notification_enabled": getattr(payment_account, "statement_notification_enabled", False),
        }

        current_app.logger.debug(">find_statement_notification_details")
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
        payment_account.name = notification_details.get("accountName")
        old_statement_notification_enabled = payment_account.statement_notification_enabled
        payment_account.statement_notification_enabled = notification_details.get("statementNotificationEnabled")
        payment_account.save()

        old_recipients = StatementRecipientsModel.find_all_recipients(auth_account_id) or []
        old_recipients_emails = [r.email for r in old_recipients]
        recipient_list = []

        # if no object is passed , dont update anything.Empty list passed means , delete everything
        if (recepients := notification_details.get("recipients")) is not None:
            StatementRecipientsModel.delete_all_recipients(payment_account.id)
            for rec in recepients or []:
                recipient = StatementRecipientsModel()
                recipient.auth_user_id = rec.get("authUserId")
                recipient.firstname = rec.get("firstname")
                recipient.lastname = rec.get("lastname")
                recipient.email = rec.get("email")
                recipient.payment_account_id = payment_account.id
                recipient_list.append(recipient)
            StatementRecipientsModel.bulk_save_recipients(recipient_list)
            new_recipients_emails = [r.email for r in recipient_list]

            if (
                old_recipients_emails != new_recipients_emails
                or old_statement_notification_enabled != notification_details.get("statementNotificationEnabled")
            ):
                ActivityLogPublisher.publish_statement_recipient_change_event(
                    StatementRecipientChange(
                        account_id=payment_account.auth_account_id,
                        old_recipients=old_recipients_emails,
                        new_recipients=new_recipients_emails,
                        statement_notification_email=payment_account.statement_notification_enabled,
                        source=QueueSources.PAY_API.value,
                    )
                )
