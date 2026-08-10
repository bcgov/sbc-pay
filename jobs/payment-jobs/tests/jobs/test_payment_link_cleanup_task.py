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

"""Tests for PaymentLinkCleanupTask (mark expired unclaimed invoices as DELETED)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code, InvoiceStatus, PaymentMethod

from tasks.payment_link_cleanup_task import PaymentLinkCleanupTask

from .factory import factory_create_direct_pay_account, factory_invoice


def _invoice_with_link(days_old: int, linked: bool = False, status: str = InvoiceStatus.CREATED.value):
    """Create a DIRECT_PAY invoice + link row `days_old` calendar days old."""
    account = factory_create_direct_pay_account(auth_account_id=f"acct-{days_old}-{linked}-{status}")
    invoice = factory_invoice(
        payment_account=account,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
        status_code=status,
    )

    link = InvoicePaymentLinkModel(token=f"tok-{invoice.id}", invoice_id=invoice.id)  # noqa: S106
    link.created_at = datetime.now(tz=UTC) - timedelta(days=days_old)
    if linked:
        link.linked_at = datetime.now(tz=UTC)
    db.session.add(link)
    db.session.commit()
    return invoice


def _set_corp_type_ttl(days: int, corp_type_code: str = "CP"):
    corp_type = CorpTypeModel.find_by_code(corp_type_code)
    corp_type.payment_link_ttl_days = days
    corp_type.save()
    cache.delete(Code.CORP_TYPE.value)


def test_cleanup_marks_expired_unclaimed_created_invoice_as_deleted(session, app):
    """Expired + unclaimed + CREATED → delete_invoice is called for it."""
    _set_corp_type_ttl(7)
    invoice = _invoice_with_link(days_old=30)

    with patch("tasks.payment_link_cleanup_task.PaymentService.delete_invoice") as mock_delete:
        count = PaymentLinkCleanupTask.cleanup_expired_links()

    assert count == 1
    mock_delete.assert_called_once_with(invoice.id)


def test_cleanup_skips_link_still_within_ttl(session, app):
    """Unclaimed but within the TTL window → NOT touched."""
    _set_corp_type_ttl(30)
    _invoice_with_link(days_old=1)

    with patch("tasks.payment_link_cleanup_task.PaymentService.delete_invoice") as mock_delete:
        count = PaymentLinkCleanupTask.cleanup_expired_links()

    assert count == 0
    mock_delete.assert_not_called()


def test_cleanup_skips_already_linked_invoice(session, app):
    """Expired but the token was already redeemed (linked_at set) → NOT touched. Link row preserved."""
    _set_corp_type_ttl(7)
    invoice = _invoice_with_link(days_old=30, linked=True)

    with patch("tasks.payment_link_cleanup_task.PaymentService.delete_invoice") as mock_delete:
        count = PaymentLinkCleanupTask.cleanup_expired_links()

    assert count == 0
    mock_delete.assert_not_called()
    # Link row still exists (audit trail).
    assert InvoicePaymentLinkModel.query.filter_by(invoice_id=invoice.id).count() == 1


def test_cleanup_skips_invoice_not_in_created_status(session, app):
    """Expired + unclaimed but invoice has moved past CREATED (e.g. PAID) → NOT touched."""
    _set_corp_type_ttl(7)
    _invoice_with_link(days_old=30, status=InvoiceStatus.PAID.value)

    with patch("tasks.payment_link_cleanup_task.PaymentService.delete_invoice") as mock_delete:
        count = PaymentLinkCleanupTask.cleanup_expired_links()

    assert count == 0
    mock_delete.assert_not_called()
