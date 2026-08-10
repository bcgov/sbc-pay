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

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code, InvoiceStatus, PaymentMethod
from tasks.express_checkout_pad_notify_task import ExpressCheckoutPadNotifyTask

from .factory import factory_create_pad_account, factory_invoice


def _enable_express_checkout(corp_type_code: str = "CP"):
    corp_type = CorpTypeModel.find_by_code(corp_type_code)
    corp_type.is_express_checkout_enabled = True
    corp_type.save()
    cache.delete(Code.CORP_TYPE.value)


def _paid_pad_invoice(paid_days_ago: int):
    """Create an express-checkout PAD invoice marked PAID `paid_days_ago` calendar days ago."""
    account = factory_create_pad_account()
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
    _enable_express_checkout()
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
    _enable_express_checkout()
    invoice = _paid_pad_invoice(paid_days_ago=0)
    _link_for(invoice.id)

    with patch("tasks.express_checkout_pad_notify_task.gcp_queue_publisher.publish_to_queue") as mock_publish:
        count = ExpressCheckoutPadNotifyTask.notify_due_invoices()

    assert count == 0
    mock_publish.assert_not_called()


def test_drain_logs_warning_and_skips_when_link_row_missing(session, app):
    """Eligible invoice with no unnotified link row → log warning + skip, don't publish."""
    _enable_express_checkout()
    invoice = _paid_pad_invoice(paid_days_ago=10)
    # Existing link row is already notified — the query filter should skip it.
    _link_for(invoice.id, notified=True)

    with (
        patch("tasks.express_checkout_pad_notify_task.gcp_queue_publisher.publish_to_queue") as mock_publish,
        patch("tasks.express_checkout_pad_notify_task.current_app.logger.warning") as mock_warn,
    ):
        count = ExpressCheckoutPadNotifyTask.notify_due_invoices()

    assert count == 0
    mock_publish.assert_not_called()
    mock_warn.assert_called()
