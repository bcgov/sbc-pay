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
    factory_payment_account, factory_premium_payment_account, get_auth_basic_user, get_auth_premium_user,
    get_pad_account_payload, get_premium_account_payload, get_basic_account_payload)


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


def test_create_pad_account(session):
    """Assert that pad account details are created."""
    pad_account = PaymentAccountService.create(get_pad_account_payload())
    assert pad_account.bank_number == get_pad_account_payload().get('paymentInfo').get('bankInstitutionNumber')
    assert pad_account.bank_account_number == get_pad_account_payload().get('paymentInfo').get('bankAccountNumber')
    assert pad_account.bank_branch_number == get_pad_account_payload().get('paymentInfo').get('bankTransitNumber')
    assert pad_account.payment_method == PaymentMethod.PAD.value
    assert pad_account.cfs_account_id
    assert pad_account.cfs_account
    assert pad_account.cfs_party
    assert pad_account.cfs_site


def test_create_pad_account_to_drawdown(session):
    """Assert updating PAD to DRAWDOWN works."""
    # Create a PAD Account first
    pad_account = PaymentAccountService.create(get_pad_account_payload())
    # Update this payment account with drawdown and assert payment method
    bcol_account = PaymentAccountService.update(pad_account.auth_account_id, get_premium_account_payload())
    assert bcol_account.auth_account_id == bcol_account.auth_account_id
    assert bcol_account.payment_method == PaymentMethod.DRAWDOWN.value


def test_create_bcol_account_to_pad(session):
    """Assert that update from BCOL to PAD works."""
    # Create a DRAWDOWN Account first
    bcol_account = PaymentAccountService.create(get_premium_account_payload())
    # Update to PAD
    pad_account = PaymentAccountService.update(bcol_account.auth_account_id, get_pad_account_payload())

    assert bcol_account.auth_account_id == bcol_account.auth_account_id
    assert pad_account.payment_method == PaymentMethod.PAD.value
    assert pad_account.cfs_account_id
    assert pad_account.cfs_account
    assert pad_account.cfs_party
    assert pad_account.cfs_site


def test_create_pad_to_bcol_to_pad(session):
    """Assert that update from BCOL to PAD works."""
    # Create a PAD Account first
    pad_account_1 = PaymentAccountService.create(get_pad_account_payload(bank_number='009'))
    assert pad_account_1.bank_number == '009'

    # Update this payment account with drawdown and assert payment method
    bcol_account = PaymentAccountService.update(pad_account_1.auth_account_id, get_premium_account_payload())
    assert bcol_account.auth_account_id == bcol_account.auth_account_id
    assert bcol_account.payment_method == PaymentMethod.DRAWDOWN.value

    # Update to PAD again
    pad_account_2 = PaymentAccountService.update(pad_account_1.auth_account_id,
                                                 get_pad_account_payload(bank_number='010'))
    assert pad_account_2.bank_number == '010'
    assert pad_account_2.payment_method == PaymentMethod.PAD.value
    assert pad_account_2.cfs_account_id != pad_account_1.cfs_account_id


def test_create_online_banking_account(session):
    """Assert that create online banking account works."""
    online_banking_account = PaymentAccountService.create(
        get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value))
    assert online_banking_account.payment_method == PaymentMethod.ONLINE_BANKING.value
    assert online_banking_account.cfs_account_id
    assert online_banking_account.cfs_account
    assert online_banking_account.cfs_party
    assert online_banking_account.cfs_site
    assert online_banking_account.bank_number is None


def test_create_online_credit_account(session):
    """Assert that create credit card account works."""
    credit_account = PaymentAccountService.create(get_basic_account_payload())
    assert credit_account.payment_method == PaymentMethod.DIRECT_PAY.value
    assert credit_account.cfs_account_id is None


def test_update_credit_to_online_banking(session):
    """Assert that update from credit card to online banking works."""
    credit_account = PaymentAccountService.create(get_basic_account_payload())
    online_banking_account = PaymentAccountService.update(credit_account.auth_account_id, get_basic_account_payload(
        payment_method=PaymentMethod.ONLINE_BANKING.value))
    assert online_banking_account.payment_method == PaymentMethod.ONLINE_BANKING.value
    assert online_banking_account.cfs_account_id
    assert online_banking_account.cfs_account
    assert online_banking_account.cfs_party
    assert online_banking_account.cfs_site
    assert online_banking_account.bank_number is None


def test_update_online_banking_to_credit(session):
    """Assert that update from online banking to credit card works."""
    online_banking_account = PaymentAccountService.create(
        get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value))
    credit_account = PaymentAccountService.update(online_banking_account.auth_account_id, get_basic_account_payload())
    assert credit_account.payment_method == PaymentMethod.DIRECT_PAY.value
