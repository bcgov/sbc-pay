# Copyright © 2019 Province of British Columbia
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
"""Service to manage PAYBC services."""
import json
from datetime import datetime, timezone

from flask import current_app
from jinja2 import Environment, FileSystemLoader
from pay_api.models.payment import PaymentAccount as PaymentAccountModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_recipients import StatementRecipients as StatementRecipientsModel
from pay_api.services import Statement as StatementService
from pay_api.services.flags import flags
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType, NotificationStatus, PaymentMethod

from utils.auth import get_token
from utils.mailer import publish_statement_notification

ENV = Environment(loader=FileSystemLoader("."), autoescape=True)


class StatementNotificationTask:  # pylint:disable=too-few-public-methods
    """Task to send statement notifications."""

    @classmethod
    def send_notifications(cls):
        """Send Notifications.

        Steps:
        1. Get all statements with Notification status as PENDING
        2. Start processing each statements
        2. Set status as processing so that if there is one more job , it wont be fetched
        3. Trigger mail
        4. Check status and update back
        """
        statements_with_pending_notifications = StatementModel.find_all_statements_by_notification_status(
            (NotificationStatus.PENDING.value,)
        )
        if statement_len := len(statements_with_pending_notifications) < 1:
            current_app.logger.info("No Statements with Pending notifications Found!")
            return

        current_app.logger.info(f"{statement_len} Statements with Pending notifications Found!")
        token = get_token()

        params = {
            "logo_url": f"{current_app.config.get('AUTH_WEB_URL')}/{current_app.config.get('REGISTRIES_LOGO_IMAGE_NAME')}",
            "url": f"{current_app.config.get('AUTH_WEB_URL')}",
        }
        template = ENV.get_template("statement_notification.html")
        for statement in statements_with_pending_notifications:
            statement.notification_status_code = NotificationStatus.PROCESSING.value
            statement.notification_date = datetime.now(tz=timezone.utc)
            statement.commit()
            payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(statement.payment_account_id)
            recipients = StatementRecipientsModel.find_all_recipients_for_payment_id(statement.payment_account_id)
            if len(recipients) < 1:
                current_app.logger.info(
                    f"No recipients found for statement: " f"{statement.payment_account_id}.Skipping sending"
                )
                statement.notification_status_code = NotificationStatus.SKIP.value
                statement.notification_date = datetime.now(tz=timezone.utc)
                statement.commit()
                continue

            to_emails = ",".join([str(recipient.email) for recipient in recipients])
            current_app.logger.info(f"Recipients email Ids:{to_emails}")
            params["org_name"] = payment_account.name
            params["frequency"] = statement.frequency.lower()
            # logic changed https://github.com/bcgov/entity/issues/4809
            # params.update({'url': params['url'].replace('orgId', payment_account.auth_account_id)})

            notification_success = True
            eft_enabled = flags.is_on("enable-eft-payment-method", default=False)
            try:
                if not payment_account.payment_method == PaymentMethod.EFT.value:
                    notification_success = cls.send_email(token, to_emails, template.render(params))
                elif eft_enabled:  # This statement template currently only used for EFT
                    result = StatementService.get_summary(payment_account.auth_account_id)
                    notification_success = publish_statement_notification(
                        payment_account, statement, result["total_due"], to_emails
                    )
                else:  # EFT not enabled - mark skip - shouldn't happen, but safeguard for manual data injection
                    statement.notification_status_code = NotificationStatus.SKIP.value
                    statement.notification_date = datetime.now(tz=timezone.utc)
                    statement.commit()
                    continue
            except Exception as e:  # NOQA # pylint:disable=broad-except
                current_app.logger.error("<notification failed")
                current_app.logger.error(e)
                notification_success = False

            if not notification_success:
                current_app.logger.error("<notification failed")
                statement.notification_status_code = NotificationStatus.FAILED.value
                statement.notification_date = datetime.now(tz=timezone.utc)
                statement.commit()
            else:
                statement.notification_status_code = NotificationStatus.SUCCESS.value
                statement.notification_date = datetime.now(tz=timezone.utc)
                statement.commit()

    @classmethod
    def send_email(cls, token, recipients: str, html_body: str):  # pylint:disable=unused-argument
        """Send the email asynchronously, using the given details."""
        subject = "Your BC Registries statement is available"
        current_app.logger.info(f"send_email to recipients: {recipients}")
        notify_url = current_app.config.get("NOTIFY_API_ENDPOINT") + "notify/"
        notify_body = {
            "recipients": recipients,
            "content": {"subject": subject, "body": html_body},
        }
        notify_response = OAuthService.post(
            notify_url,
            token=token,
            auth_header_type=AuthHeaderType.BEARER,
            content_type=ContentType.JSON,
            data=notify_body,
        )
        current_app.logger.info("send_email notify_response")
        if notify_response:
            response_json = json.loads(notify_response.text)
            if response_json.get("notifyStatus", "FAILURE") != "FAILURE":
                return True

        return False
