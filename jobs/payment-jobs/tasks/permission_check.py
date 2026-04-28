# Copyright © 2026 Province of British Columbia
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
"""Task do basic integration permission check without affecting data."""

from flask import current_app

from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.enums import QueueSources


class PayJobPermissionCheckTask:  # pylint: disable=too-few-public-methods
    """Validate job permissions."""

    @classmethod
    def check(cls):
        """Attempt operations that require permissions."""
        # test auth activity log access
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_JOBS.value,
                message_type="HELLO",
                payload={"hello": "world"},
                topic=current_app.config.get("AUTH_EVENT_TOPIC"),
            )
        )
        # test auth account mailer access
        gcp_queue_publisher.publish_to_queue(
            gcp_queue_publisher.QueueMessage(
                source=QueueSources.PAY_JOBS.value,
                message_type="HELLO",
                payload={"hello": "world"},
                topic=current_app.config.get("ACCOUNT_MAILER_TOPIC"),
            )
        )
