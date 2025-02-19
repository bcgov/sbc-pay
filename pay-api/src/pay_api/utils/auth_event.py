"""Common code that sends AUTH events."""

from dataclasses import asdict, dataclass
from typing import Any, Optional

from flask import current_app
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message

from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.enums import QueueSources


class AuthEvent:
    """Publishes to the auth-queue as an auth event though PUBSUB, this message gets sent to account-mailer after."""

    @dataclass
    class LockAccountDetails:
        """Lock account details."""

        pay_account: Any
        additional_emails: str = ""
        payment_method: Optional[str] = None
        source: Optional[str] = None
        suspension_reason_code: Optional[str] = None
        outstanding_amount: Optional[float] = None
        original_amount: Optional[float] = None
        amount: Optional[float] = None

    @staticmethod
    def publish_lock_account_event(params: LockAccountDetails):
        """Publish NSF lock account event to the auth queue."""
        pay_account = params.pay_account
        additional_emails = params.additional_emails
        payment_method = params.payment_method
        source = params.source
        suspension_reason_code = params.suspension_reason_code
        outstanding_amount = params.outstanding_amount
        original_amount = params.original_amount
        amount = params.amount
        try:
            lock_payload = {
                "accountId": pay_account.auth_account_id,
                "paymentMethod": payment_method,
                "suspensionReasonCode": suspension_reason_code,
                "additionalEmails": additional_emails,
                "outstandingAmount": outstanding_amount,
                "originalAmount": original_amount,
                "amount": amount,
            }
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=source,
                    message_type=QueueMessageTypes.NSF_LOCK_ACCOUNT.value,
                    payload=lock_payload,
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
                    pay_account.auth_account_id}, {lock_payload}.",
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
