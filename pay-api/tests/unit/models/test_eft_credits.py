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

"""Tests to assure the EFT Credits model.

Test-Suite to ensure that the EFT Credits model is working as expected.
"""
from datetime import datetime
from typing import List

from pay_api.models import EFTCredit, EFTFile, EFTShortnames
from tests.utilities.base_test import factory_payment_account


def test_eft_credits(session):
    """Assert eft credits defaults are stored."""
    payment_account = factory_payment_account()
    payment_account.save()

    assert payment_account.id is not None

    eft_short_name = EFTShortnames()
    eft_short_name.auth_account_id = payment_account.auth_account_id
    eft_short_name.short_name = 'TESTSHORTNAME'
    eft_short_name.save()

    eft_file = EFTFile()
    eft_file.file_ref = 'test.txt'
    eft_file.save()

    eft_credit = EFTCredit()
    eft_credit.eft_file_id = eft_file.id
    eft_credit.short_name_id = eft_short_name.id
    eft_credit.amount = 100.00
    eft_credit.remaining_amount = 50.00
    eft_credit.save()

    assert eft_credit.id is not None
    assert eft_credit.payment_account_id is None
    assert eft_credit.eft_file_id == eft_file.id
    assert eft_credit.created_on.date() == datetime.now().date()
    assert eft_credit.amount == 100.00
    assert eft_credit.remaining_amount == 50.00

    eft_credit.payment_account_id = payment_account.id
    eft_credit.save()

    assert eft_credit.payment_account_id == payment_account.id

    eft_credits: List[EFTCredit] = EFTCredit.find_by_payment_account_id(payment_account.id)

    assert eft_credits is not None
    assert eft_credits[0].id == eft_credit.id
