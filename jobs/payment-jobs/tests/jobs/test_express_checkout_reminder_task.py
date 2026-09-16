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

"""Tests for ExpressCheckoutReminderTask (one-time payer reminder for unclaimed invoices)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.utils.enums import PaymentMethod
from tasks.express_checkout_reminder_task import ExpressCheckoutReminderTask

from .factory import factory_create_direct_pay_account, factory_invoice


def _created_invoice(created_days_ago: int = 2, total: float = 100.0, auth_account_id: str = "sa-partner-1"):
    """Return a CREATED DIRECT_PAY invoice `created_days_ago` days old."""
    account = factory_create_direct_pay_account(auth_account_id=auth_account_id)
    account.save()
    return factory_invoice(
        payment_account=account,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
        total=total,
        created_on=datetime.now(tz=UTC) - timedelta(days=created_days_ago),
    )


def _link_for(
    invoice_id: int,
    email: str | None = "payer@example.com",
    created_days_ago: int = 2,
    notified: bool = False,
    linked: bool = False,
):
    """Create an invoice_payment_links row for the invoice."""
    link = InvoicePaymentLinkModel(token=f"tok-{invoice_id}", invoice_id=invoice_id)  # noqa: S106
    link.email = email
    link.created_at = datetime.now(tz=UTC) - timedelta(days=created_days_ago)
    if notified:
        link.notified_at = datetime.now(tz=UTC)
    if linked:
        link.linked_at = datetime.now(tz=UTC)
    db.session.add(link)
    db.session.commit()
    return link


def _run_task():
    """Run the reminder task with the PubSub publish mocked out."""
    with patch("tasks.express_checkout_reminder_task.publish_express_checkout_reminder") as mock_publish:
        count = ExpressCheckoutReminderTask.notify_unpaid_invoices()
    return count, mock_publish


def test_sends_reminder_and_stamps_notified_at(session, app):
    """Invoice old enough, has email, unclaimed — reminder sent and notified_at stamped."""
    invoice = _created_invoice(created_days_ago=2)
    link = _link_for(invoice.id, created_days_ago=2)

    count, mock_publish = _run_task()

    assert count == 1
    mock_publish.assert_called_once()
    _, kwargs = mock_publish.call_args
    assert kwargs["email"] == "payer@example.com"
    assert "pay/" in kwargs["payment_url"]
    assert kwargs["total"] == "100.00"
    assert kwargs["description"] == ""
    # corp_type.payment_link_ttl_days is None → falls back to PAYMENT_LINK_TOKEN_TTL_DAYS=30; link is 2 days old
    assert kwargs["expiry_days"] == 28
    assert kwargs["expiry_date"] != ""
    assert InvoicePaymentLinkModel.find_by_token(link.token).notified_at is not None


def test_expiry_uses_corp_type_ttl(session, app):
    """Corp type payment_link_ttl_days overrides the config default."""
    invoice = _created_invoice(created_days_ago=2)
    corp_type = db.session.query(CorpTypeModel).filter_by(code=invoice.corp_type_code).first()
    corp_type.payment_link_ttl_days = 7
    db.session.commit()
    _link_for(invoice.id, created_days_ago=2)

    _, mock_publish = _run_task()

    _, kwargs = mock_publish.call_args
    assert kwargs["expiry_days"] == 5  # 7 day TTL − 2 days elapsed


@pytest.mark.parametrize(
    "invoice_days,link_kwargs",
    [
        (0, {"created_days_ago": 0}),  # link too new
        (2, {"notified": True}),  # already notified
        (2, {"linked": True}),  # already redeemed
        (2, {"email": None}),  # no email supplied
    ],
)
def test_skips_reminder(session, app, invoice_days, link_kwargs):
    """Links that don't qualify for a reminder are silently skipped."""
    invoice = _created_invoice(created_days_ago=invoice_days)
    _link_for(invoice.id, **link_kwargs)

    count, mock_publish = _run_task()

    assert count == 0
    mock_publish.assert_not_called()


def test_skips_invoice_without_link_row(session, app):
    """Invoice with no link row (non-express-checkout) is never touched."""
    account = factory_create_direct_pay_account(auth_account_id="regular-acct")
    account.save()
    factory_invoice(
        payment_account=account,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
        created_on=datetime.now(tz=UTC) - timedelta(days=2),
    )

    count, mock_publish = _run_task()

    assert count == 0
    mock_publish.assert_not_called()


def test_notified_at_not_stamped_when_publish_fails(session, app):
    """If publish raises, notified_at is NOT stamped so the next run retries."""
    invoice = _created_invoice(created_days_ago=2)
    link = _link_for(invoice.id)

    with patch(
        "tasks.express_checkout_reminder_task.publish_express_checkout_reminder",
        side_effect=Exception("PubSub unavailable"),
    ):
        count = ExpressCheckoutReminderTask.notify_unpaid_invoices()

    assert count == 0
    assert InvoicePaymentLinkModel.find_by_token(link.token).notified_at is None
