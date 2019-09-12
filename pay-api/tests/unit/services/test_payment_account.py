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

from pay_api.models import PaymentAccount
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService


def factory_payment_account(corp_number: str = 'CP0001234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def test_account_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()

    pa = PaymentAccountService.find_account(payment_account.corp_number, payment_account.corp_type_code,
                                            payment_account.payment_system_code)

    assert pa is not None
    assert pa.id is not None
    assert pa.corp_number is not None
    assert pa.corp_type_code is not None
    assert pa.payment_system_code is not None
    assert pa.asdict() is not None


def test_account_find_by_id(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()

    pa = PaymentAccountService.find_by_id(payment_account.id)

    assert pa is not None
    assert pa.id is not None
    assert pa.corp_number is not None
    assert pa.corp_type_code is not None
    assert pa.payment_system_code is not None
    assert pa.asdict() is not None


def test_account_invalid_lookup(session):
    """Invalid account test."""
    p = PaymentAccountService.find_account('1234', 'CP', 'PAYBC')

    assert p is not None
    assert p.id is None
    import pytest
    from pay_api.exceptions import BusinessException
    from pay_api.utils.errors import Error
    with pytest.raises(BusinessException) as excinfo:
        PaymentAccountService.find_account(None, None, None)
    assert excinfo.value.status == Error.PAY004.status


def test_account_find_by_invalid_id(session):
    """Invalid account test."""
    import pytest
    from pay_api.exceptions import BusinessException
    from pay_api.utils.errors import Error
    with pytest.raises(BusinessException) as excinfo:
        PaymentAccountService.find_by_id(999)
    assert excinfo.value.status == Error.PAY009.status
