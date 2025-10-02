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

from datetime import datetime
from unittest.mock import patch

import pytest
import pytz

from pay_api.services.activity_log_publisher import ActivityLogPublisher
from pay_api.utils.dataclasses import (
    AccountLockEvent,
    AccountUnlockEvent,
    PaymentInfoChangeEvent,
    PaymentMethodChangeEvent,
    StatementIntervalChangeEvent,
    StatementRecipientChangeEvent,
)
from pay_api.utils.enums import ActivityAction, PaymentMethod, QueueSources


@pytest.mark.parametrize(
    "old_frequency,new_frequency,effective_date,expected_value",
    [
        ("WEEKLY", "MONTHLY", None, "Weekly|Monthly"),
        ("DAILY", "WEEKLY", None, "Daily|Weekly"),
        (None, "MONTHLY", None, "None|Monthly"),
        ("WEEKLY", None, None, "Weekly|None"),
        ("DAILY", "DAILY", None, "Daily|Daily"),
        ("WEEKLY", "MONTHLY", datetime(2024, 1, 15, 10, 30, 0, tzinfo=pytz.UTC), "Weekly|Monthly|2024-01-15"),
        ("DAILY", "WEEKLY", datetime(2024, 1, 15, 8, 0, 0, tzinfo=pytz.UTC), "Daily|Weekly|2024-01-15"),
        (None, "MONTHLY", datetime(2024, 1, 15, 16, 0, 0, tzinfo=pytz.UTC), "None|Monthly|2024-01-15"),
    ],
)
@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_statement_interval_change_frequency_combinations(
    mock_publish, old_frequency, new_frequency, effective_date, expected_value, session, client, jwt, app
):
    """Test statement interval change with different frequency combinations."""
    params = StatementIntervalChangeEvent(
        account_id="test-account-123",
        old_frequency=old_frequency,
        new_frequency=new_frequency,
        effective_date=effective_date,
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_statement_interval_change_event(params)

    mock_publish.assert_called_once()
    call_args = mock_publish.call_args[0][0]
    payload = call_args.payload
    assert payload["itemValue"] == expected_value


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
    params = StatementRecipientChangeEvent(
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
    assert payload["itemValue"] == expected_value


@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_publish_payment_info_change_event(mock_publish, session, client, jwt, app):
    """Test payment info change event publishing."""
    params = PaymentInfoChangeEvent(
        account_id="test-account-123",
        payment_method=PaymentMethod.PAD.value,
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_payment_info_change_event(params)

    mock_publish.assert_called_once()
    call_args = mock_publish.call_args[0][0]
    payload = call_args.payload
    assert payload["action"] == ActivityAction.PAYMENT_INFO_CHANGE.value
    assert payload["orgId"] == "test-account-123"
    assert payload["itemValue"] == "Pre Authorized Debit"


@pytest.mark.parametrize(
    "old_method,new_method,expected_value",
    [
        ("PAD", "EFT", "Pre Authorized Debit|Electronic Funds Transfer"),
        ("EFT", "PAD", "Electronic Funds Transfer|Pre Authorized Debit"),
        ("CC", "ONLINE_BANKING", "Credit Card|Online Banking"),
        (None, "PAD", "Pre Authorized Debit"),
        ("PAD", "PAD", "Pre Authorized Debit|Pre Authorized Debit"),
    ],
)
@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_publish_payment_method_change_event_combinations(
    mock_publish, old_method, new_method, expected_value, session, client, jwt, app
):
    """Test payment method change event with different method combinations."""
    params = PaymentMethodChangeEvent(
        account_id="test-account-123",
        old_method=old_method,
        new_method=new_method,
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_payment_method_change_event(params)

    if old_method == new_method:
        mock_publish.assert_not_called()
    else:
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        payload = call_args.payload
        assert payload["action"] == ActivityAction.PAYMENT_METHOD_CHANGE.value
        assert payload["orgId"] == "test-account-123"
        assert payload["itemValue"] == expected_value


@pytest.mark.parametrize(
    "payment_method,expected_action,should_publish",
    [
        (PaymentMethod.PAD.value, ActivityAction.PAD_NSF_LOCK.value, True),
        (PaymentMethod.EFT.value, ActivityAction.EFT_OVERDUE_LOCK.value, True),
        ("UNSUPPORTED", None, False),
    ],
)
@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_publish_lock_event_payment_methods(
    mock_publish, payment_method, expected_action, should_publish, session, client, jwt, app
):
    """Test lock event publishing for different payment methods and unsupported methods."""
    params = AccountLockEvent(
        account_id="test-account-123",
        current_payment_method=payment_method,
        reason="Test lock reason",
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_lock_event(params)

    if should_publish:
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        payload = call_args.payload
        assert payload["action"] == expected_action
        assert payload["orgId"] == "test-account-123"
        assert payload["itemValue"] == "Test lock reason"
    else:
        mock_publish.assert_not_called()


@pytest.mark.parametrize(
    "payment_method,expected_action,should_publish",
    [
        (PaymentMethod.PAD.value, ActivityAction.PAD_NSF_UNLOCK.value, True),
        (PaymentMethod.EFT.value, ActivityAction.EFT_OVERDUE_UNLOCK.value, True),
        ("UNSUPPORTED", None, False),
    ],
)
@patch("pay_api.services.activity_log_publisher.gcp_queue_publisher.publish_to_queue")
def test_publish_unlock_event_payment_methods(
    mock_publish, payment_method, expected_action, should_publish, session, client, jwt, app
):
    """Test unlock event publishing for different payment methods and unsupported methods."""
    params = AccountUnlockEvent(
        account_id="test-account-123",
        current_payment_method=payment_method,
        unlock_payment_method=PaymentMethod.CC.value,
        source=QueueSources.PAY_API.value,
    )

    ActivityLogPublisher.publish_unlock_event(params)

    if should_publish:
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        payload = call_args.payload
        assert payload["action"] == expected_action
        assert payload["orgId"] == "test-account-123"
    else:
        mock_publish.assert_not_called()
