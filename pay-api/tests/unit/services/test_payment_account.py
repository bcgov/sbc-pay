# Copyright © 2019 Province of British Columbia
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

"""Tests to assure the FeeSchedule Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import PaymentMethod

from tests.utilities.base_test import (
    factory_payment_account, factory_premium_payment_account, get_auth_basic_user, get_auth_premium_user)


def test_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()

    pa = PaymentAccountService.find_account(get_auth_basic_user())

    assert pa is not None
    assert pa.id is not None


def test_direct_pay_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()

    pa = PaymentAccountService.find_account(get_auth_basic_user())

    assert pa is not None
    assert pa.id is not None


def test_premium_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_premium_payment_account()
    payment_account.save()

    pa = PaymentAccountService.find_account(get_auth_premium_user())

    assert pa is not None
    assert pa.id is not None
