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

from typing import Dict

from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import PaymentMethod

from tests.utilities.base_test import (
    factory_payment_account, factory_premium_payment_account, get_auth_basic_user, get_auth_premium_user)


def test_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    business_info: Dict = {
        'businessIdentifier': payment_account.corp_number,
        'corpType': payment_account.corp_type_code
    }

    pa = PaymentAccountService.find_account(business_info, get_auth_basic_user(), 'PAYBC', PaymentMethod.CC.value)

    assert pa is not None
    assert pa.id is not None
    assert pa.corp_number is not None
    assert pa.corp_type_code is not None


def test_direct_pay_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()
    business_info: Dict = {
        'businessIdentifier': payment_account.corp_number,
        'corpType': payment_account.corp_type_code
    }

    pa = PaymentAccountService.find_account(business_info, get_auth_basic_user(), 'PAYBC',
                                            PaymentMethod.DIRECT_PAY.value)

    assert pa is not None
    assert pa.id is not None
    assert pa.corp_number is not None
    assert pa.corp_type_code is not None


def test_premium_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_premium_payment_account()
    payment_account.save()

    pa = PaymentAccountService.find_account({}, get_auth_premium_user(),
                                            payment_system='BCOL', payment_method=PaymentMethod.DRAWDOWN.value)

    assert pa is not None
    assert pa.id is not None


def test_account_invalid_lookup(session):
    """Invalid account test."""
    business_info: Dict = {
        'businessIdentifier': '1234',
        'corpType': 'CP'
    }

    p = PaymentAccountService.find_account(business_info, get_auth_basic_user(), 'PAYBC', PaymentMethod.CC.value)

    assert p is not None
    assert p.id is None
    import pytest
    from pay_api.exceptions import BusinessException
    from pay_api.utils.errors import Error
    with pytest.raises(BusinessException) as excinfo:
        PaymentAccountService.find_account({}, get_auth_basic_user(), 'PAYBC', PaymentMethod.CC.value)
    assert excinfo.value.code == Error.INVALID_CORP_OR_FILING_TYPE.name


def test_account_invalid_premium_account_lookup(session):
    """Invalid account test."""
    business_info: Dict = {
    }

    p = PaymentAccountService.find_account(business_info, get_auth_premium_user(), 'BCOL', PaymentMethod.DRAWDOWN.value)

    assert p is not None
    assert p.id is None
    import pytest
    from pay_api.exceptions import BusinessException
    from pay_api.utils.errors import Error
    with pytest.raises(BusinessException) as excinfo:
        PaymentAccountService.find_account(business_info, {}, 'BCOL', PaymentMethod.DRAWDOWN.value)
    assert excinfo.value.code == Error.INCOMPLETE_ACCOUNT_SETUP.name
