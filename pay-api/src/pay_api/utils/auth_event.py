"""Common code that sends AUTH events."""

from typing import Optional

from attrs import define
from flask import current_app
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services import gcp_queue_publisher
from pay_api.services.activity_log_publisher import ActivityLogPublisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.dataclasses import AccountLockEvent, AccountUnlockEvent
from pay_api.utils.enums import PaymentMethod, QueueSources
from pay_api.utils.serializable import Serializable


@define
class LockAccountDetails(Serializable):
    """Lock account details."""

    account_id: str
    additional_emails: str = ""
    payment_method: Optional[str] = None
    source: Optional[str] = None
    # Generic suspension reason code shown on the staff dashboard
    suspension_reason_code: Optional[str] = None
    outstanding_amount: Optional[float] = None
    original_amount: Optional[float] = None
    amount: Optional[float] = None
    # Contains NSF reason or Statement ids that were overdue for EFT
    reversal_reason: Optional[str] = None


class AuthEvent:
    """Publishes to the auth-queue as an auth event though PUBSUB, this message gets sent to account-mailer after."""

    @staticmethod
    def publish_lock_account_event(params: LockAccountDetails):
        """Publish NSF lock account event to the auth queue."""
        try:
            lock_payload = params.to_dict()
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=params.source,
                    message_type=QueueMessageTypes.NSF_LOCK_ACCOUNT.value,
                    payload=lock_payload,
                    topic=current_app.config.get("AUTH_EVENT_TOPIC"),
                )
            )
            ActivityLogPublisher.publish_lock_event(
                AccountLockEvent(
                    account_id=params.account_id,
                    current_payment_method=params.payment_method,
                    reason=params.reversal_reason,
                    source=params.source,
                )
            )
        except Exception:  # NOQA pylint: disable=broad-except
            current_app.logger.error("Error publishing lock event:", exc_info=True)
            current_app.logger.warning(
                f"Notification to Queue failed for the Account {
                    params.account_id}"
            )

    @staticmethod
    def publish_unlock_account_event(payment_account: PaymentAccountModel):
        """Publish EFT overdue unlock event to the auth queue."""
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
            ActivityLogPublisher.publish_unlock_event(
                AccountUnlockEvent(
                    account_id=payment_account.auth_account_id,
                    current_payment_method=payment_account.payment_method,
                    unlock_payment_method=PaymentMethod.EFT.value,
                    source=QueueSources.PAY_JOBS.value,
                )
            )
        except Exception:  # NOQA pylint: disable=broad-except
            current_app.logger.error("Error publishing EFT overdue unlock event:", exc_info=True)
            current_app.logger.warning(
                f"Notification to Queue failed for the Account {
                    payment_account.auth_account_id}"
            )
