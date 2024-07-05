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

"""Tests to assure the CreateAccountTask.

Test-Suite to ensure that the CreateAccountTask is working as expected.
"""
from unittest.mock import patch

import requests
from pay_api.models import CfsAccount, PaymentAccount
from pay_api.services.online_banking_service import OnlineBankingService
from pay_api.services.pad_service import PadService
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod
from requests.exceptions import HTTPError

from tasks.cfs_create_account_task import CreateAccountTask
from utils import mailer

from .factory import factory_create_eft_account, factory_create_online_banking_account, factory_create_pad_account


def test_create_account_setup(session):
    """Test create account."""
    CreateAccountTask.create_accounts()
    assert True


def test_create_pad_account(session):
    """Test create account."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id='1')
    CreateAccountTask.create_accounts()
    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.PENDING_PAD_ACTIVATION.value
    assert cfs_account.bank_account_number
    assert cfs_account.cfs_party
    assert cfs_account.cfs_site
    assert cfs_account.cfs_account
    assert cfs_account.payment_instrument_number


def test_create_eft_account(session):
    """Test create account."""
    # Create a pending account first, then call the job
    account = factory_create_eft_account(auth_account_id='1')
    CreateAccountTask.create_accounts()
    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.EFT.value)
    assert cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert cfs_account.payment_instrument_number is None


def test_create_pad_account_user_error(session):
    """Test create account."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id='1')
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.PENDING.value
    mock_response = requests.models.Response()
    mock_response.headers['CAS-Returned-Messages'] = '[Errors = [34] Bank Account Number is Invalid]'
    mock_response.status_code = 404

    side_effect = HTTPError(response=mock_response)
    with patch.object(mailer, 'publish_mailer_events') as mock_mailer:
        with patch('pay_api.services.CFSService.create_cfs_account', side_effect=side_effect):
            CreateAccountTask.create_accounts()
            mock_mailer.assert_called

    account = PaymentAccount.find_by_id(account.id)
    cfs_account: CfsAccount = CfsAccount.find_by_id(cfs_account.id)
    assert cfs_account.status == CfsAccountStatus.INACTIVE.value


def test_create_pad_account_system_error(session):
    """Test create account."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id='1')
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.PENDING.value
    mock_response = requests.models.Response()
    mock_response.headers['CAS-Returned-Messages'] = '[CFS Down]'
    mock_response.status_code = 404

    side_effect = HTTPError(response=mock_response)
    with patch.object(mailer, 'publish_mailer_events') as mock_mailer:
        with patch('pay_api.services.CFSService.create_cfs_account', side_effect=side_effect):
            CreateAccountTask.create_accounts()
            mock_mailer.assert_not_called()

    account = PaymentAccount.find_by_id(account.id)
    cfs_account: CfsAccount = CfsAccount.find_by_id(cfs_account.id)
    assert cfs_account.status == CfsAccountStatus.PENDING.value


def test_create_pad_account_no_confirmation_period(session):
    """Test create account.Arbitrary scenario when there is no confirmation period."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id='1', confirmation_period=0)
    CreateAccountTask.create_accounts()
    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert cfs_account.bank_account_number
    assert cfs_account.cfs_party
    assert cfs_account.cfs_site
    assert cfs_account.cfs_account
    assert cfs_account.payment_instrument_number


def test_create_online_banking_account(session):
    """Test create account."""
    # Create a pending account first, then call the job
    account = factory_create_online_banking_account(auth_account_id='2')
    CreateAccountTask.create_accounts()
    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)
    assert cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert not cfs_account.bank_account_number
    assert cfs_account.cfs_party
    assert cfs_account.cfs_site
    assert cfs_account.cfs_account
    assert cfs_account.payment_instrument_number is None


def test_update_online_banking_account(session):
    """Test update account."""
    # Create a pending account first, then call the job
    account = factory_create_online_banking_account(auth_account_id='2')
    CreateAccountTask.create_accounts()
    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)

    # Update account, which shouldn't change any details
    OnlineBankingService().update_account(name='Test', cfs_account=cfs_account, payment_info=None)
    updated_cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)

    assert updated_cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert cfs_account.id == updated_cfs_account.id


def test_update_pad_account(session):
    """Test update account."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id='2')
    CreateAccountTask.create_accounts()

    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)

    assert cfs_account.payment_instrument_number

    # Now update the account.
    new_payment_details = {
        'bankInstitutionNumber': '111',
        'bankTransitNumber': '222',
        'bankAccountNumber': '3333333333'
    }
    PadService().update_account(name='Test', cfs_account=cfs_account, payment_info=new_payment_details)
    cfs_account = CfsAccount.find_by_id(cfs_account.id)

    # Run the job again
    CreateAccountTask.create_accounts()

    updated_cfs_account: CfsAccount = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert updated_cfs_account.id != cfs_account.id
    assert updated_cfs_account.bank_account_number == new_payment_details.get('bankAccountNumber')
    assert updated_cfs_account.bank_branch_number == new_payment_details.get('bankTransitNumber')
    assert updated_cfs_account.bank_number == new_payment_details.get('bankInstitutionNumber')

    assert cfs_account.status == CfsAccountStatus.INACTIVE.value
    assert updated_cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert updated_cfs_account.payment_instrument_number
