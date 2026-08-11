# Copyright © 2026 Province of British Columbia
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

"""Tests for ExpressCheckoutPadNotifyTask (drain the held PAD partner notifications)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.utils.enums import InvoiceStatus, PaymentMethod

from tasks.express_checkout_pad_notify_task import ExpressCheckoutPadNotifyTask

from .factory import factory_create_pad_account, factory_invoice


def _paid_pad_invoice(paid_days_ago: int, auth_account_id: str = "acct-1"):
    """Create a PAD invoice marked PAID `paid_days_ago` calendar days ago."""
    account = factory_create_pad_account(auth_account_id=auth_account_id)
    invoice = factory_invoice(payment_account=account, payment_method_code=PaymentMethod.PAD.value)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_date = datetime.now(tz=UTC) - timedelta(days=paid_days_ago)
    invoice.save()
    return invoice


def _link_for(invoice_id: int, notified: bool = False):
    link = InvoicePaymentLinkModel(token=f"tok-{invoice_id}", invoice_id=invoice_id)  # noqa: S106
    link.linked_at = datetime.now(tz=UTC)
    if notified:
        link.partner_notified_at = datetime.now(tz=UTC)
    db.session.add(link)
    db.session.commit()
    return link


def test_drain_publishes_and_stamps_when_past_hold_window(session, app):
    """Invoice paid 10 calendar days ago is well past the 3-business-day hold — publish + stamp."""
    invoice = _paid_pad_invoice(paid_days_ago=10)
    link = _link_for(invoice.id)

    with patch("tasks.express_checkout_pad_notify_task.gcp_queue_publisher.publish_to_queue") as mock_publish:
        count = ExpressCheckoutPadNotifyTask.notify_due_invoices()

    assert count == 1
    mock_publish.assert_called_once()
    refreshed = InvoicePaymentLinkModel.find_by_token(link.token)
    assert refreshed.partner_notified_at is not None


def test_drain_skips_when_still_within_hold_window(session, app):
    """Invoice paid earlier today — inside the hold window; must NOT publish."""
    invoice = _paid_pad_invoice(paid_days_ago=0)
    _link_for(invoice.id)

    with patch("tasks.express_checkout_pad_notify_task.gcp_queue_publisher.publish_to_queue") as mock_publish:
        count = ExpressCheckoutPadNotifyTask.notify_due_invoices()

    assert count == 0
    mock_publish.assert_not_called()


def test_drain_skips_when_already_notified(session, app):
    """Link row with partner_notified_at set — INNER JOIN filter excludes it. Idempotent across runs."""
    invoice = _paid_pad_invoice(paid_days_ago=10)
    _link_for(invoice.id, notified=True)

    with patch("tasks.express_checkout_pad_notify_task.gcp_queue_publisher.publish_to_queue") as mock_publish:
        count = ExpressCheckoutPadNotifyTask.notify_due_invoices()

    assert count == 0
    mock_publish.assert_not_called()


def test_drain_ignores_regular_pad_invoice_without_link_row(session, app):
    """Regular PAD invoice (no invoice_payment_links row) is NOT express-checkout — drain skips it."""
    _paid_pad_invoice(paid_days_ago=10)  # no _link_for() call — regular customer

    with patch("tasks.express_checkout_pad_notify_task.gcp_queue_publisher.publish_to_queue") as mock_publish:
        count = ExpressCheckoutPadNotifyTask.notify_due_invoices()

    assert count == 0
    mock_publish.assert_not_called()
