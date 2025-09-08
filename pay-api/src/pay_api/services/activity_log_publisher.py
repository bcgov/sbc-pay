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
from pay_api.utils.converter import Converter
from pay_api.utils.dataclasses import ActivityLogData, StatementIntervalChange, StatementRecipientChange
from pay_api.utils.enums import ActivityAction, QueueSources


class ActivityLogPublisher:
    """Publishes activity log events to the queue."""

    @staticmethod
    def _publish_activity_event(activity_data: ActivityLogData):
        """Publish activity events to the queue."""
        try:
            payload = Converter(snake_case_to_camel=True).unstructure(activity_data)
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
    def publish_statement_interval_change_event(params: StatementIntervalChange):
        """Publish statement interval change event to the activity log queue."""
        activity_data = ActivityLogData(
            actor_id=params.account_id,
            action=ActivityAction.STATEMENT_INTERVAL_CHANGE.value,
            item_name=None,
            item_id=params.account_id,
            item_value=f"{params.old_frequency.title()}|{params.new_frequency.title()}",
            org_id=params.account_id,
            remote_addr=request.remote_addr if request else None,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            item_type="ACCOUNT",
        )
        ActivityLogPublisher._publish_activity_event(activity_data)

    @staticmethod
    def publish_statement_recipient_change_event(params: StatementRecipientChange):
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

        activity_data = ActivityLogData(
            actor_id=params.account_id,
            action=ActivityAction.STATEMENT_RECIPIENT_CHANGE.value,
            item_name=None,
            item_id=params.account_id,
            item_value=f"{old_recipients_str}|{new_recipients_str}",
            org_id=params.account_id,
            remote_addr=request.remote_addr if request else None,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            item_type="ACCOUNT",
        )
        ActivityLogPublisher._publish_activity_event(activity_data)
