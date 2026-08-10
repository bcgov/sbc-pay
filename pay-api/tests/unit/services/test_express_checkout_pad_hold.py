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

"""Tests for the express-checkout PAD notification hold pieces."""

from datetime import UTC, datetime
from unittest.mock import patch

from pay_api.models import CorpType as CorpTypeModel
from pay_api.services.pad_service import PadService
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code, PaymentMethod
from pay_api.utils.util import subtract_business_days
from tests.utilities.base_test import factory_invoice, factory_payment_account


def _fresh_invoice(payment_method: str, corp_type_code: str = "CP"):
    account = factory_payment_account()
    account.save()
    invoice = factory_invoice(payment_account=account, payment_method_code=payment_method, corp_type_code=corp_type_code)
    invoice.save()
    return invoice


def _enable_express_checkout(corp_type_code: str = "CP"):
    corp_type = CorpTypeModel.find_by_code(corp_type_code)
    corp_type.is_express_checkout_enabled = True
    corp_type.save()
    cache.delete(Code.CORP_TYPE.value)


def test_pad_complete_post_invoice_skips_publish_for_express_checkout(session, app):
    """Create-time publish is suppressed for express-checkout PAD invoices."""
    _enable_express_checkout()
    invoice = _fresh_invoice(payment_method=PaymentMethod.PAD.value)

    with patch.object(PadService, "release_payment_or_reversal") as mock_release:
        PadService().complete_post_invoice(invoice, invoice_reference=None)
    mock_release.assert_not_called()


def test_pad_complete_post_invoice_publishes_regular(session, app):
    """Regular (non-express-checkout) PAD publishes at create-time as today."""
    # CP corp type is not express-checkout-enabled by default.
    invoice = _fresh_invoice(payment_method=PaymentMethod.PAD.value)

    with patch.object(PadService, "release_payment_or_reversal") as mock_release:
        PadService().complete_post_invoice(invoice, invoice_reference=None)
    mock_release.assert_called_once()


def test_subtract_business_days_skips_weekend(session, app):
    """3 business days back from Wed lands on the prior Fri (skipping Sat/Sun)."""
    wed = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)  # 2026-08-12 is a Wednesday
    # -1 biz day → Tue 08-11; -2 → Mon 08-10; -3 → Fri 08-07
    result = subtract_business_days(wed, 3)
    assert result.date().isoformat() == "2026-08-07"


def test_subtract_business_days_skips_stat_holiday(session, app):
    """Labour Day 2026 (Mon 2026-09-07) is skipped when counting back."""
    # 2026-09-08 is Tuesday. 1 biz day back would be Fri 2026-09-04 (Sat/Sun/Mon-holiday skipped).
    tue_after_labour_day = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    result = subtract_business_days(tue_after_labour_day, 1)
    assert result.date().isoformat() == "2026-09-04"
