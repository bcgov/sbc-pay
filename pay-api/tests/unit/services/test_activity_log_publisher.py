# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test for the activity log publisher service.

Test-Suite to ensure that the Activity Log Publisher Service is working as expected.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pay_api.services.activity_log_publisher import ActivityLogPublisher
from pay_api.utils.dataclasses import ActivityLogData, StatementIntervalChange, StatementRecipientChange
from pay_api.utils.enums import ActivityAction, QueueSources


@pytest.mark.parametrize(
    "old_frequency,new_frequency,expected_value",
    [
        ("WEEKLY", "MONTHLY", "Weekly|Monthly"),
        ("DAILY", "WEEKLY", "Daily|Weekly"),
        (None, "MONTHLY", "None|Monthly"),
        ("WEEKLY", None, "Weekly|None"),
        ("DAILY", "DAILY", "Daily|Daily"),
    ],
)
@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_statement_interval_change_frequency_combinations(
    mock_publish, old_frequency, new_frequency, expected_value, session, client, jwt, app
):
    """Test statement interval change with different frequency combinations."""
    params = StatementIntervalChange(
        account_id="test-account-123",
        old_frequency=old_frequency,
        new_frequency=new_frequency,
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_statement_interval_change_event(params)

    mock_publish.assert_called_once()
    call_args = mock_publish.call_args[0][0]
    payload = call_args.payload
    assert payload["item_value"] == expected_value


@pytest.mark.parametrize(
    "old_recipients,new_recipients,statement_notification_email,expected_value",
    [
        (["old1@example.com"], ["new1@example.com"], True, "old1@example.com|new1@example.com|enabled"),
        (["old1@example.com"], ["new1@example.com"], False, "old1@example.com|new1@example.com|disabled"),
        (
            ["old1@example.com", "old2@example.com"],
            ["new1@example.com"],
            True,
            "old1@example.com,old2@example.com|new1@example.com|enabled",
        ),
        ([], ["new1@example.com"], True, "None|new1@example.com|enabled"),
        (["old1@example.com"], [], False, "old1@example.com|None|disabled"),
        (None, ["new1@example.com"], True, "None|new1@example.com|enabled"),
        (["old1@example.com"], None, False, "old1@example.com|None|disabled"),
        (None, None, False, "None|None|disabled"),
        (["same@example.com"], ["same@example.com"], True, "same@example.com|same@example.com|enabled"),
    ],
)
@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_statement_recipient_change_recipient_combinations(
    mock_publish,
    old_recipients,
    new_recipients,
    statement_notification_email,
    expected_value,
    session,
    client,
    jwt,
    app,
):
    """Test statement recipient change with different recipient combinations."""
    params = StatementRecipientChange(
        account_id="test-account-123",
        old_recipients=old_recipients,
        new_recipients=new_recipients,
        statement_notification_email=statement_notification_email,
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_statement_recipient_change_event(params)

    mock_publish.assert_called_once()
    call_args = mock_publish.call_args[0][0]
    payload = call_args.payload
    assert payload["item_value"] == expected_value
