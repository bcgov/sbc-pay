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
"""Service to publish activity log events."""

from datetime import datetime, timezone

from flask import current_app, request
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.dataclasses import (
    ActivityLogData,
    EftOverdueLockEvent,
    EftOverdueUnlockEvent,
    PadNsfLockEvent,
    PadNsfUnlockEvent,
    PaymentInfoChangeEvent,
    PaymentMethodChangeEvent,
    StatementIntervalChangeEvent,
    StatementRecipientChangeEvent,
)
from pay_api.utils.enums import ActivityAction, QueueSources
from pay_api.utils.user_context import UserContext, user_context


class ActivityLogPublisher:
    """Publishes activity log events to the queue."""

    @staticmethod
    def _publish_activity_event(activity_data: ActivityLogData):
        """Publish activity events to the queue."""
        try:
            payload = activity_data.to_dict()
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.PAY_API.value,
                    message_type=QueueMessageTypes.ACTIVITY_LOG.value,
                    payload=payload,
                    topic=current_app.config.get("AUTH_EVENT_TOPIC"),
                )
            )
            current_app.logger.info(f"{activity_data.action} event published for account {activity_data.item_id}")
        except Exception:  # NOQA pylint: disable=broad-except
            current_app.logger.error(
                f"Error publishing {activity_data.action} event for {activity_data.item_id}:", exc_info=True
            )

    @staticmethod
    @user_context
    def _create_and_publish_activity_event(
        action: str, account_id: str, item_value: str, item_name: str = "", **kwargs
    ):
        """Create and publish a standard activity event."""
        user: UserContext = kwargs["user"]
        activity_data = ActivityLogData(
            actor_id=user.sub,
            action=action,
            item_name=item_name,
            item_id=account_id,
            item_value=item_value,
            org_id=account_id,
            remote_addr=request.remote_addr if request else None,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            item_type="ACCOUNT",
        )
        ActivityLogPublisher._publish_activity_event(activity_data)

    @staticmethod
    @user_context
    def publish_statement_interval_change_event(params: StatementIntervalChangeEvent, **kwargs):
        """Publish statement interval change event to the activity log queue."""
        user: UserContext = kwargs["user"]
        activity_data = ActivityLogData(
            actor_id=user.sub,
            action=ActivityAction.STATEMENT_INTERVAL_CHANGE.value,
            item_name=None,
            item_id=params.account_id,
            item_value=f"{str(params.old_frequency).title()}|{str(params.new_frequency).title()}",
            org_id=params.account_id,
            remote_addr=request.remote_addr if request else None,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            item_type="ACCOUNT",
        )
        ActivityLogPublisher._publish_activity_event(activity_data)

    @staticmethod
    @user_context
    def publish_statement_recipient_change_event(params: StatementRecipientChangeEvent, **kwargs):
        """Publish statement recipient change event to the activity log queue."""
        user: UserContext = kwargs["user"]
        old_recipients_str = (
            ",".join(params.old_recipients).lower()
            if params.old_recipients and len(params.old_recipients) > 0
            else "None"
        )
        new_recipients_str = (
            ",".join(params.new_recipients).lower()
            if params.new_recipients and len(params.new_recipients) > 0
            else "None"
        )
        statement_notification_email_str = "enabled" if params.statement_notification_email else "disabled"

        activity_data = ActivityLogData(
            actor_id=user.sub,
            action=ActivityAction.STATEMENT_RECIPIENT_CHANGE.value,
            item_name=None,
            item_id=params.account_id,
            item_value=f"{old_recipients_str}|{new_recipients_str}|{statement_notification_email_str}",
            org_id=params.account_id,
            remote_addr=request.remote_addr if request else None,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            item_type="ACCOUNT",
        )
        ActivityLogPublisher._publish_activity_event(activity_data)

    @staticmethod
    @user_context
    def publish_pad_nsf_lock_event(params: PadNsfLockEvent, **kwargs):
        """Publish PAD NSF lock event to the activity log queue."""
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.PAD_NSF_LOCK.value, account_id=params.account_id, item_value=params.reason, **kwargs
        )

    @staticmethod
    @user_context
    def publish_pad_nsf_unlock_event(params: PadNsfUnlockEvent, **kwargs):
        """Publish PAD NSF unlock event to the activity log queue."""
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.PAD_NSF_UNLOCK.value,
            account_id=params.account_id,
            item_value=params.payment_method,
            **kwargs,
        )

    @staticmethod
    @user_context
    def publish_eft_overdue_lock_event(params: EftOverdueLockEvent, **kwargs):
        """Publish EFT overdue lock event to the activity log queue."""
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.EFT_OVERDUE_LOCK.value,
            account_id=params.account_id,
            item_value=params.statement_numbers,
            **kwargs,
        )

    @staticmethod
    @user_context
    def publish_eft_overdue_unlock_event(params: EftOverdueUnlockEvent, **kwargs):
        """Publish EFT overdue unlock event to the activity log queue."""
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.EFT_OVERDUE_UNLOCK.value,
            account_id=params.account_id,
            item_value=params.payment_method,
            **kwargs,
        )

    @staticmethod
    @user_context
    def publish_payment_method_change_event(params: PaymentMethodChangeEvent, **kwargs):
        """Publish payment method change event to the activity log queue."""
        if params.old_method and params.new_method:
            item_value = f"{params.old_method}|{params.new_method}"
        else:
            item_value = params.new_method or params.old_method or ""

        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.PAYMENT_METHOD_CHANGE.value,
            account_id=params.account_id,
            item_value=item_value,
            **kwargs,
        )

    @staticmethod
    @user_context
    def publish_payment_info_change_event(params: PaymentInfoChangeEvent, **kwargs):
        """Publish payment info change event to the activity log queue."""
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.PAYMENT_INFO_CHANGE.value,
            account_id=params.account_id,
            item_value=params.payment_method,
            **kwargs,
        )
