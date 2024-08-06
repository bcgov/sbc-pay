# Copyright © 2023 Province of British Columbia
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

"""Tests to assure the EFT Short names historical model.

Test-Suite to ensure that the EFT Short names historical model is working as expected.
"""
from datetime import datetime, timezone

from pay_api.models import EFTShortnamesHistorical
from pay_api.utils.enums import EFTHistoricalTypes
from tests.utilities.base_test import factory_eft_shortname, factory_payment_account


def test_eft_short_names_historical(session):
    """Assert eft short names historical data is stored."""
    payment_account = factory_payment_account()
    payment_account.save()

    assert payment_account.id is not None

    eft_short_name = factory_eft_shortname('TESTSHORTNAME')
    eft_short_name.save()

    now_date = datetime.now(tz=timezone.utc).date()
    default_historical = EFTShortnamesHistorical(
        amount=151.50,
        created_by='USER1',
        credit_balance=1234.50,
        short_name_id=eft_short_name.id,
        transaction_date=now_date,
        transaction_type=EFTHistoricalTypes.FUNDS_RECEIVED.value
    ).save()

    default_historical = EFTShortnamesHistorical.find_by_id(default_historical.id)
    assert default_historical.id is not None
    assert default_historical.amount == 151.50
    assert default_historical.created_on.date() == now_date
    assert default_historical.created_by == 'USER1'
    assert default_historical.credit_balance == 1234.50
    assert not default_historical.hidden
    assert not default_historical.is_processing
    assert default_historical.payment_account_id is None
    assert default_historical.related_group_link_id is None
    assert default_historical.short_name_id == eft_short_name.id
    assert default_historical.statement_number is None
    assert default_historical.transaction_date.date() == now_date
    assert default_historical.transaction_type == EFTHistoricalTypes.FUNDS_RECEIVED.value

    short_name_historical = EFTShortnamesHistorical(
        amount=123.50,
        created_by='USER1',
        credit_balance=456.50,
        hidden=True,
        is_processing=True,
        payment_account_id=payment_account.id,
        related_group_link_id=5,
        short_name_id=eft_short_name.id,
        statement_number=1234567,
        transaction_date=now_date,
        transaction_type=EFTHistoricalTypes.STATEMENT_PAID.value
    ).save()

    short_name_historical = EFTShortnamesHistorical.find_by_id(short_name_historical.id)

    assert short_name_historical.id is not None
    assert short_name_historical.amount == 123.50
    assert short_name_historical.created_on.date() == now_date
    assert short_name_historical.created_by == 'USER1'
    assert short_name_historical.credit_balance == 456.50
    assert short_name_historical.hidden
    assert short_name_historical.is_processing
    assert short_name_historical.payment_account_id == payment_account.id
    assert short_name_historical.related_group_link_id == 5
    assert short_name_historical.short_name_id == eft_short_name.id
    assert short_name_historical.statement_number == 1234567
    assert short_name_historical.transaction_date.date() == now_date
    assert short_name_historical.transaction_type == EFTHistoricalTypes.STATEMENT_PAID.value
