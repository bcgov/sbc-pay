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

import base64
import json
from unittest.mock import patch

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.services.email_service import send_email, send_receipt_notification
from pay_api.services.invoice import Invoice as InvoiceService
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


def _paid_invoice(auth_account_id: str, unredeemed_link: bool = False, link_email: str = None):
    """Create a paid invoice, optionally with an unredeemed payment link."""
    payment_account = factory_payment_account(auth_account_id=auth_account_id)
    payment_account.save()
    invoice = factory_invoice(payment_account, status_code=InvoiceStatus.PAID.value)
    invoice.save()
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value).save()
    if unredeemed_link:
        InvoicePaymentLinkModel(token=f"tok-{invoice.id}", invoice_id=invoice.id, email=link_email).save()
    return invoice


def test_receipt_notification_reaches_admins_and_coordinators(session, app):
    """The ticket is addressed to the owner and coordinators, so both roles are requested."""
    invoice = _paid_invoice("1234")

    with patch("pay_api.services.email_service.get_account_members", return_value=ADMIN_MEMBERS) as mock_users:
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(invoice)

    assert mock_users.call_args.kwargs["roles"] == "ADMIN,COORDINATOR"
    assert mock_send.call_args.args[0] == ["owner@example.com", "coordinator@example.com"]


def test_receipt_notification_skipped_when_guest_left_no_email(session, app):
    """No account and no address the partner gave us — there is nobody to tell."""
    invoice = _paid_invoice("sa-partner-client", unredeemed_link=True)

    with patch("pay_api.services.email_service.get_account_members") as mock_users:
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(invoice)

    mock_users.assert_not_called()
    mock_send.assert_not_called()


def test_receipt_notification_skips_members_without_an_email(session, app):
    """A member whose contact carries no email must not end up in the recipient list."""
    invoice = _paid_invoice("1234")
    members = {"members": [{"user": {"contacts": [{}]}}, {"user": {"contacts": [{"email": "owner@example.com"}]}}]}

    with patch("pay_api.services.email_service.get_account_members", return_value=members):
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(invoice)

    assert mock_send.call_args.args[0] == ["owner@example.com"]


def test_receipt_notification_goes_to_the_guest_email(session, app):
    """An unredeemed link carries the payer's address, so the receipt goes there."""
    invoice = _paid_invoice("sa-partner-client", unredeemed_link=True, link_email="payer@example.com")

    with patch("pay_api.services.email_service.get_account_members") as mock_users:
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(invoice)

    mock_users.assert_not_called()
    assert mock_send.call_args.args[0] == ["payer@example.com"]
    # The guest template drops the account rows — they have no account.
    assert "Account number" not in mock_send.call_args.args[2]


def test_receipt_notification_accepts_the_invoice_service_object(session, app):
    """The service wrapper has no `payment_account` relationship, only `payment_account_id`.

    Every pay-api call site passes that wrapper rather than the model.
    """
    model_invoice = _paid_invoice("1234")
    service_invoice = InvoiceService.find_by_id(model_invoice.id, skip_auth_check=True)
    assert not hasattr(service_invoice, "payment_account")

    with patch("pay_api.services.email_service.get_account_members", return_value=ADMIN_MEMBERS):
        with patch("pay_api.services.email_service.send_email_async") as mock_send:
            send_receipt_notification(service_invoice)

    assert mock_send.call_args.args[0] == ["owner@example.com", "coordinator@example.com"]


def test_receipt_notification_attaches_the_receipt_pdf(session, app):
    """A settled invoice ships the receipt, which is what the email body promises."""
    invoice = _paid_invoice("1234")

    with patch("pay_api.services.email_service.get_account_members", return_value=ADMIN_MEMBERS):
        with patch("pay_api.services.email_service.ReceiptService.create_receipt", return_value=[b"%PDF-", b"fake"]):
            with patch("pay_api.services.email_service.send_email_async") as mock_send:
                send_receipt_notification(invoice)

    attachments = mock_send.call_args.args[3]
    assert base64.b64decode(attachments[0]["fileBytes"]) == b"%PDF-fake"
    # notify-api's AttachmentRequest contract — a wrong key is silently dropped.
    assert attachments[0] == {
        "fileName": f"bcregistry-receipt-{invoice.id}.pdf",
        "fileBytes": attachments[0]["fileBytes"],
        "attachOrder": "1",
    }


def test_receipt_notification_still_sends_when_the_receipt_cannot_be_built(session, app):
    """report-api failing must not cost the payer their confirmation email."""
    invoice = _paid_invoice("1234")

    with patch("pay_api.services.email_service.get_account_members", return_value=ADMIN_MEMBERS):
        with patch(
            "pay_api.services.email_service.ReceiptService.create_receipt", side_effect=Exception("report-api down")
        ):
            with patch("pay_api.services.email_service.send_email_async") as mock_send:
                send_receipt_notification(invoice)

    assert mock_send.call_args.args[0] == ["owner@example.com", "coordinator@example.com"]
    assert mock_send.call_args.args[3] == []


def test_receipt_notification_leaves_the_pending_decision_to_the_receipt_service(session, app):
    """Whether a pending invoice has a receipt is the receipt service's call, not ours.

    It refuses an unpaid card invoice and renders a "payment pending" receipt for PAD and
    EFT, so this module asks unconditionally and attaches whatever comes back.
    """
    invoice = _paid_invoice("1234")
    invoice.invoice_status_code = InvoiceStatus.APPROVED.value
    invoice.save()

    with patch("pay_api.services.email_service.get_account_members", return_value=ADMIN_MEMBERS):
        with patch(
            "pay_api.services.email_service.ReceiptService.create_receipt", return_value=[b"%PDF-pending"]
        ) as mock_receipt:
            with patch("pay_api.services.email_service.send_email_async") as mock_send:
                send_receipt_notification(invoice)

    mock_receipt.assert_called_once()
    assert base64.b64decode(mock_send.call_args.args[3][0]["fileBytes"]) == b"%PDF-pending"
