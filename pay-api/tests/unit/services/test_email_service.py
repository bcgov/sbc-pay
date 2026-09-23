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

from sbc_common_components.utils.enums import QueueMessageTypes

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.services.email_service import send_email, send_receipt_notification
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.utils.enums import (
    AuthHeaderType,
    ContentType,
    InvoiceReferenceStatus,
    InvoiceStatus,
)
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment_account,
    factory_receipt,
)


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


def _paid_invoice(auth_account_id: str, unredeemed_link: bool = False, link_email: str = None):
    """Create a paid invoice, optionally with an unredeemed payment link."""
    payment_account = factory_payment_account(auth_account_id=auth_account_id)
    payment_account.save()
    invoice = factory_invoice(payment_account, status_code=InvoiceStatus.PAID.value)
    invoice.save()
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value).save()
    factory_receipt(invoice.id).save()
    if unredeemed_link:
        InvoicePaymentLinkModel(token=f"tok-{invoice.id}", invoice_id=invoice.id, email=link_email).save()
    return invoice


def _published(invoice):
    """Run send_receipt_notification and return what it put on the mailer topic, or None."""
    with patch("pay_api.services.email_service.gcp_queue_publisher.publish_to_queue") as mock_publish:
        send_receipt_notification(invoice)
    return mock_publish.call_args.args[0] if mock_publish.called else None


def test_receipt_notification_goes_to_the_account(session, app):
    """account-mailer looks up the admins and coordinators, so only the account id is sent."""
    invoice = _paid_invoice("1234")

    message = _published(invoice)

    assert message.message_type == QueueMessageTypes.PAYMENT_RECEIPT.value
    assert message.topic == app.config.get("ACCOUNT_MAILER_TOPIC")
    assert message.payload["accountId"] == "1234"
    assert "emailAddresses" not in message.payload
    assert message.payload["invoiceId"] == invoice.id


def test_receipt_notification_goes_to_the_guest_email(session, app):
    """An unredeemed link carries the payer's address, and there is no account to name."""
    invoice = _paid_invoice("sa-partner-client", unredeemed_link=True, link_email="payer@example.com")

    message = _published(invoice)

    assert message.payload["emailAddresses"] == "payer@example.com"
    assert "accountId" not in message.payload


def test_receipt_notification_skipped_when_guest_left_no_email(session, app):
    """No account and no address the partner gave us — there is nobody to tell."""
    invoice = _paid_invoice("sa-partner-client", unredeemed_link=True)

    assert _published(invoice) is None


def test_receipt_notification_accepts_the_invoice_service_object(session, app):
    """The service wrapper has no `payment_account` relationship, only `payment_account_id`.

    Every pay-api call site passes that wrapper rather than the model.
    """
    model_invoice = _paid_invoice("1234")
    service_invoice = InvoiceService.find_by_id(model_invoice.id, skip_auth_check=True)
    assert not hasattr(service_invoice, "payment_account")

    assert _published(service_invoice).payload["accountId"] == "1234"


def test_receipt_notification_carries_the_receipt_vars(session, app):
    """account-mailer renders the PDF from these, so they must survive the queue's json encoding."""
    invoice = _paid_invoice("1234")

    payload = _published(invoice).payload

    json.dumps(payload)
    assert payload["templateVars"]["invoice"]["id"] == invoice.id
    assert payload["templateVars"]["receiptNumber"]
    assert payload["templateVars"]["filingDateTime"]


def test_receipt_notification_still_sent_without_receipt_vars(session, app):
    """A receipt that can't be described yet must not cost the payer their confirmation email."""
    invoice = _paid_invoice("1234")

    with patch(
        "pay_api.services.email_service.ReceiptService.get_receipt_details", side_effect=Exception("no receipt")
    ):
        message = _published(invoice)

    assert message.payload["templateVars"] is None
