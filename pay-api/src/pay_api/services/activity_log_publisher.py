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
from pay_api.services.code import Code as CodeService
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.dataclasses import (
    AccountLockEvent,
    AccountUnlockEvent,
    ActivityLogData,
    PaymentInfoChangeEvent,
    PaymentMethodChangeEvent,
    StatementIntervalChangeEvent,
    StatementRecipientChangeEvent,
)
from pay_api.utils.enums import ActivityAction, Code, PaymentMethod, QueueSources
from pay_api.utils.user_context import UserContext, user_context


class ActivityLogPublisher:
    """Publishes activity log events to the queue."""

    @staticmethod
    def _get_payment_method_description(payment_method_code: str) -> str:
        """Get payment method description from code."""
        if not payment_method_code:
            return payment_method_code

        method = CodeService.find_code_value_by_type_and_code(Code.PAYMENT_METHODS.value, payment_method_code)
        return method.get("description", payment_method_code) if method else payment_method_code

    @staticmethod
    def _publish_activity_event(activity_data: ActivityLogData):
        """Publish activity events to the queue."""
        try:
            payload = activity_data.to_dict()
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=activity_data.source,
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
        action: str,
        account_id: str,
        item_value: str,
        item_name: str = "",
        source: str = QueueSources.PAY_API.value,
        **kwargs,
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
            source=source,
            item_type="ACCOUNT",
        )
        ActivityLogPublisher._publish_activity_event(activity_data)

    @staticmethod
    def publish_statement_interval_change_event(params: StatementIntervalChangeEvent):
        """Publish statement interval change event to the activity log queue."""
        item_value = f"{str(params.old_frequency).title()}|{str(params.new_frequency).title()}"
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.STATEMENT_INTERVAL_CHANGE.value,
            account_id=params.account_id,
            item_value=item_value,
            source=params.source,
        )

    @staticmethod
    def publish_statement_recipient_change_event(params: StatementRecipientChangeEvent):
        """Publish statement recipient change event to the activity log queue."""
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
        item_value = f"{old_recipients_str}|{new_recipients_str}|{statement_notification_email_str}"

        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.STATEMENT_RECIPIENT_CHANGE.value,
            account_id=params.account_id,
            item_value=item_value,
            source=params.source,
        )

    @staticmethod
    def publish_payment_method_change_event(params: PaymentMethodChangeEvent):
        """Publish payment method change event to the activity log queue."""
        if params.old_method == params.new_method:
            return

        old_method_description = ActivityLogPublisher._get_payment_method_description(params.old_method or "")
        new_method_description = ActivityLogPublisher._get_payment_method_description(params.new_method or "")
        item_value = (
            new_method_description
            if not old_method_description
            else f"{old_method_description}|{new_method_description}"
        )

        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.PAYMENT_METHOD_CHANGE.value,
            account_id=params.account_id,
            item_value=item_value,
            source=params.source,
        )

    @staticmethod
    def publish_payment_info_change_event(params: PaymentInfoChangeEvent):
        """Publish payment info change event to the activity log queue."""
        payment_method_description = ActivityLogPublisher._get_payment_method_description(params.payment_method)
        ActivityLogPublisher._create_and_publish_activity_event(
            action=ActivityAction.PAYMENT_INFO_CHANGE.value,
            account_id=params.account_id,
            item_value=payment_method_description,
            source=params.source,
        )

    @staticmethod
    def publish_unlock_event(params: AccountUnlockEvent):
        """Publish unlock event to the activity log queue based on payment method."""
        unlock_actions = {
            PaymentMethod.PAD.value: ActivityAction.PAD_NSF_UNLOCK.value,
            PaymentMethod.EFT.value: ActivityAction.EFT_OVERDUE_UNLOCK.value,
        }

        action = unlock_actions.get(params.current_payment_method)
        if not action:
            current_app.logger.error(f"Unsupported payment method for unlock event: {params.current_payment_method}")
            return

        unlock_payment_method_description = ActivityLogPublisher._get_payment_method_description(
            params.unlock_payment_method
        )
        ActivityLogPublisher._create_and_publish_activity_event(
            action=action,
            account_id=params.account_id,
            item_value=unlock_payment_method_description,
            source=params.source,
        )

    @staticmethod
    def publish_lock_event(params: AccountLockEvent):
        """Publish lock event to the activity log queue based on payment method."""
        lock_actions = {
            PaymentMethod.PAD.value: ActivityAction.PAD_NSF_LOCK.value,
            PaymentMethod.EFT.value: ActivityAction.EFT_OVERDUE_LOCK.value,
        }

        action = lock_actions.get(params.current_payment_method)
        if not action:
            current_app.logger.error(f"Unsupported payment method for lock event: {params.current_payment_method}")
            return

        ActivityLogPublisher._create_and_publish_activity_event(
            action=action,
            account_id=params.account_id,
            item_value=params.reason,
            source=params.source,
        )
