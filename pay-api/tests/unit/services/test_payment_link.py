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

"""Tests for PaymentLinkService (express-checkout token lifecycle)."""

from datetime import UTC, datetime, timedelta

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.services.payment_link import PaymentLinkService
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code
from tests.utilities.base_test import factory_invoice, factory_payment_account


def _make_link(days_old: int = 0, linked: bool = False):
    """Create an invoice + link row `days_old` old, optionally already linked."""
    account = factory_payment_account()
    account.save()
    invoice = factory_invoice(payment_account=account)
    invoice.save()

    link = InvoicePaymentLinkModel(token="tok-test-token", invoice_id=invoice.id)  # noqa: S106
    link.created_at = datetime.now(tz=UTC) - timedelta(days=days_old)
    if linked:
        link.linked_at = datetime.now(tz=UTC)
    db.session.add(link)
    db.session.commit()
    return link


def test_attach_payment_link_adds_payment_url(session, app):
    """attach_payment_link merges a paymentUrl and persists a link row."""
    account = factory_payment_account()
    account.save()
    invoice = factory_invoice(payment_account=account)
    invoice.save()

    dto = PaymentLinkService.attach_payment_link({"id": invoice.id})

    assert dto.get("paymentUrl")
    assert InvoicePaymentLinkModel.query.filter_by(invoice_id=invoice.id).count() == 1


def test_resolve_token_accepts_fresh_unlinked(session, app):
    """resolve_token returns the link row for a fresh, unlinked token."""
    link = _make_link(days_old=1)
    assert PaymentLinkService.resolve_token(link.token).token == link.token


def test_resolve_token_rejects_expired(session, app):
    """resolve_token rejects a token older than the corp-type TTL."""
    corp_type = CorpTypeModel.find_by_code("CP")
    corp_type.payment_link_ttl_days = 7
    corp_type.save()
    cache.delete(Code.CORP_TYPE.value)

    link = _make_link(days_old=30)

    with pytest.raises(BusinessException):
        PaymentLinkService.resolve_token(link.token)


def test_resolve_token_rejects_consumed_by_default(session, app):
    """resolve_token rejects an already-linked token unless allow_linked=True."""
    link = _make_link(days_old=0, linked=True)

    with pytest.raises(BusinessException):
        PaymentLinkService.resolve_token(link.token)


def test_resolve_token_allows_consumed_when_flag_set(session, app):
    """resolve_token returns a consumed token when allow_linked=True (idempotent re-visit)."""
    link = _make_link(days_old=0, linked=True)
    assert PaymentLinkService.resolve_token(link.token, allow_linked=True).token == link.token
