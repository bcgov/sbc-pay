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

"""Tests to assure the statement recipients end-point.

Test-Suite to ensure that the /accounts/{account_id}/statements/notifications endpoint is working as expected.
"""

import json
from unittest.mock import patch

import pytest

from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models.invoice import Invoice
from pay_api.models.payment_account import PaymentAccount
from pay_api.models.statement_recipients import StatementRecipients as StatementRecipientsModel
from pay_api.utils.enums import QueueSources
from tests.utilities.base_test import get_claims, get_payment_request, token_header


def test_get_statement_notifications(session, client, jwt, app):
    """Test that the statement notifications can be retrieved."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/notifications",
        headers=headers,
    )

    assert rv.status_code == 200
    assert "recipients" in rv.json
    assert "statementNotificationEnabled" in rv.json


def test_post_statement_notifications_add_recipients(session, client, jwt, app):
    """Test that the statement notifications can be added."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)

    request_data = {
        "recipients": [{"authUserId": 123, "firstname": "John", "lastname": "Doe", "email": "john@example.com"}],
        "statementNotificationEnabled": True,
        "accountName": "Test Account",
    }

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/notifications",
        data=json.dumps(request_data),
        headers=headers,
    )

    assert rv.status_code == 201


@pytest.mark.parametrize(
    "recipients,expected_old,expected_new,should_publish",
    [
        (
            [{"authUserId": 123, "firstname": "John", "lastname": "Doe", "email": "john@example.com"}],
            [],
            ["john@example.com"],
            True,
        ),
        (
            [{"authUserId": 124, "firstname": "Jane", "lastname": "Smith", "email": "jane@example.com"}],
            [],
            ["jane@example.com"],
            True,
        ),
        ([], [], [], False),
    ],
)
@patch("pay_api.services.statement_recipients.ActivityLogPublisher.publish_statement_recipient_change_event")
def test_post_statement_notifications_activity_log_add_recipients(
    mock_publish, recipients, expected_old, expected_new, should_publish, session, client, jwt, app
):
    """Test that the statement notifications can be updated."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)

    request_data = {"recipients": recipients, "statementNotificationEnabled": True, "accountName": "Test Account"}

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/notifications",
        data=json.dumps(request_data),
        headers=headers,
    )

    assert rv.status_code == 201
    if should_publish:
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        assert call_args.account_id == pay_account.auth_account_id
        assert call_args.old_recipients == expected_old
        assert call_args.new_recipients == expected_new
        assert call_args.source == QueueSources.PAY_API.value
    else:
        mock_publish.assert_not_called()


@pytest.mark.parametrize(
    "old_recipients,new_recipients,should_publish",
    [
        (
            [{"authUserId": 123, "firstname": "John", "lastname": "Doe", "email": "john@example.com"}],
            [{"authUserId": 124, "firstname": "Jane", "lastname": "Smith", "email": "jane@example.com"}],
            True,
        ),
    ],
)
@patch("pay_api.services.statement_recipients.ActivityLogPublisher.publish_statement_recipient_change_event")
def test_post_statement_notifications_activity_log_update_recipients(
    mock_publish, old_recipients, new_recipients, should_publish, session, client, jwt, app
):
    """Test that the statement notifications can be updated."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)

    old_request_data = {
        "recipients": old_recipients,
        "statementNotificationEnabled": True,
        "accountName": "Test Account",
    }

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/notifications",
        data=json.dumps(old_request_data),
        headers=headers,
    )
    mock_publish.reset_mock()

    new_request_data = {
        "recipients": new_recipients,
        "statementNotificationEnabled": True,
        "accountName": "Test Account",
    }

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/notifications",
        data=json.dumps(new_request_data),
        headers=headers,
    )

    assert rv.status_code == 201
    if should_publish:
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        assert call_args.account_id == pay_account.auth_account_id
        old_emails = [r["email"] for r in old_recipients] if old_recipients else []
        new_emails = [r["email"] for r in new_recipients] if new_recipients else []
        assert call_args.old_recipients == old_emails
        assert call_args.new_recipients == new_emails
        assert call_args.source == QueueSources.PAY_API.value
    else:
        mock_publish.assert_not_called()
