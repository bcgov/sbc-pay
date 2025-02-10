"""Common code that sends AUTH events."""

from flask import current_app
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.enums import PaymentMethod, QueueSources, SuspensionReasonCodes
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message


class AuthEvent:
    """Publishes to the auth-queue as an auth event though PUBSUB, this message gets sent to account-mailer after."""

    @staticmethod
    def publish_lock_account_event(pay_account: PaymentAccountModel, additional_emails="", payment_method=None):
        """Publish NSF lock account event to the auth queue."""
        try:
            payload = AuthEvent._create_event_payload(pay_account, additional_emails, payment_method)
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.PAY_JOBS.value,
                    message_type=QueueMessageTypes.NSF_LOCK_ACCOUNT.value,
                    payload=payload,
                    topic=current_app.config.get("AUTH_EVENT_TOPIC"),
                )
            )
        except Exception:  # NOQA pylint: disable=broad-except
            current_app.logger.error("Error publishing lock event:", exc_info=True)
            current_app.logger.warning(
                f"Notification to Queue failed for the Account {
                                       pay_account.auth_account_id} - {pay_account.name}"
            )
            capture_message(
                f"Notification to Queue failed for the Account {
                            pay_account.auth_account_id}, {payload}.",
                level="error",
            )

    @staticmethod
    def publish_unlock_account_event(payment_account: PaymentAccountModel):
        """Publish NSF unlock event to the auth queue."""
        try:
            unlock_payload = {
                "accountId": payment_account.auth_account_id,
                "skipNotification": True,
            }
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.PAY_JOBS.value,
                    message_type=QueueMessageTypes.NSF_UNLOCK_ACCOUNT.value,
                    payload=unlock_payload,
                    topic=current_app.config.get("AUTH_EVENT_TOPIC"),
                )
            )
        except Exception:  # NOQA pylint: disable=broad-except
            current_app.logger.error("Error publishing NSF unlock event:", exc_info=True)
            current_app.logger.warning(
                f"Notification to Queue failed for the Account {
                                       payment_account.auth_account_id} - {payment_account.name}"
            )
            capture_message(
                f"Notification to Queue failed for the Account {
                            payment_account.auth_account_id}, {unlock_payload}.",
                level="error",
            )

    @staticmethod
    def _create_event_payload(pay_account, additional_emails="", payment_method=None):
        return {
            "accountId": pay_account.auth_account_id,
            "paymentMethod": payment_method,
            "suspensionReasonCode": SuspensionReasonCodes.OVERDUE_EFT.value,
            "additionalEmails": additional_emails,
        }
