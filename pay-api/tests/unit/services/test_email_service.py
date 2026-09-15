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

"""Tests for Email Service."""

import json
from unittest.mock import patch

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.services.email_service import send_email, send_receipt_notification
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus
from tests.utilities.base_test import factory_invoice, factory_invoice_reference, factory_payment_account


def test_send_email(app, monkeypatch):
    """Test send email."""
    app.config["NOTIFY_API_ENDPOINT"] = "http://test_notify_api_endpoint/"

    monkeypatch.setattr("pay_api.services.email_service.get_service_account_token", lambda: "test")

    with app.app_context():
        with patch("pay_api.services.email_service.OAuthService.post") as mock_post:
            mock_post.return_value.text = json.dumps({"notifyStatus": "SUCCESS"})
            result = send_email(["recipient@example.com"], "Subject", "Body")
            mock_post.assert_called_with(
                "http://test_notify_api_endpoint/notify/",
                token="test",  # noqa: S106
                auth_header_type=AuthHeaderType.BEARER,
                content_type=ContentType.JSON,
                data={
                    "recipients": "recipient@example.com",
                    "content": {"subject": "Subject", "body": "Body"},
                },
            )
        assert result is True


ADMIN_MEMBERS = {
    "members": [
        {"user": {"contacts": [{"email": "owner@example.com"}]}},
        {"user": {"contacts": [{"email": "coordinator@example.com"}]}},
    ]
}


def _paid_invoice(auth_account_id: str, unredeemed_link: bool = False):
    """Return a settled invoice sitting on the given auth account.

    `unredeemed_link` adds the payment-link row an express-checkout invoice carries,
    left unclaimed — the state an anonymous payer leaves behind.
    """
    payment_account = factory_payment_account(auth_account_id=auth_account_id)
    payment_account.save()
    invoice = factory_invoice(payment_account, status_code=InvoiceStatus.PAID.value)
    invoice.save()
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value).save()
    if unredeemed_link:
        InvoicePaymentLinkModel(token=f"tok-{invoice.id}", invoice_id=invoice.id).save()
    return invoice


def test_receipt_notification_reaches_admins_and_coordinators(session, app):
    """Both roles are asked for — the ticket is addressed to the owner *and* coordinators."""
    invoice = _paid_invoice("1234")

    with patch("pay_api.services.email_service.get_account_admin_users", return_value=ADMIN_MEMBERS) as mock_users:
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(invoice)

    assert mock_users.call_args.kwargs["roles"] == "ADMIN,COORDINATOR"
    assert mock_send.call_args.args[0] == ["owner@example.com", "coordinator@example.com"]


def test_receipt_notification_skipped_for_anonymous_payment(session, app):
    """An express-checkout invoice never redeemed has no real account, so nobody to notify."""
    invoice = _paid_invoice("sa-partner-client", unredeemed_link=True)

    with patch("pay_api.services.email_service.get_account_admin_users") as mock_users:
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(invoice)

    mock_users.assert_not_called()
    mock_send.assert_not_called()
