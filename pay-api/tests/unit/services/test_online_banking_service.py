# Copyright © 2024 Province of British Columbia
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

"""Tests to assure the Online Banking service layer.

Test-Suite to ensure that the Online Banking layer is working as expected.
"""

from unittest.mock import patch

from pay_api.services.cfs_service import CFSService
from pay_api.services.online_banking_service import OnlineBankingService
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod

online_banking_service = OnlineBankingService()


def test_create_account_without_contact_info(session):
    """Assert that create_account returns PENDING when no contact_info is provided."""
    account = online_banking_service.create_account(identifier="100", contact_info={}, payment_info={})
    assert account
    assert account.status == CfsAccountStatus.PENDING.value
    assert account.payment_method == PaymentMethod.ONLINE_BANKING.value
    assert account.cfs_account is None
    assert account.cfs_party is None
    assert account.cfs_site is None


def test_create_account_with_contact_info(session):
    """Assert that create_account provisions the CFS account synchronously when contact_info is provided."""
    contact_info = {
        "addressLine1": "1000 Douglas Street",
        "city": "Victoria",
        "province": "BC",
        "postalCode": "V8V1V1",
        "country": "CA",
    }
    account = online_banking_service.create_account(identifier="200", contact_info=contact_info, payment_info={})
    assert account
    assert account.status == CfsAccountStatus.ACTIVE.value
    assert account.payment_method == PaymentMethod.ONLINE_BANKING.value
    assert account.cfs_account
    assert account.cfs_party
    assert account.cfs_site


def test_create_account_falls_open_on_cfs_error(session):
    """Assert that a CAS failure returns PENDING so the caller can proceed and the job can retry."""
    contact_info = {
        "addressLine1": "1000 Douglas Street",
        "city": "Victoria",
        "province": "BC",
        "postalCode": "V8V1V1",
        "country": "CA",
    }
    with patch.object(CFSService, "create_cfs_account", side_effect=Exception("CAS boom")):
        account = online_banking_service.create_account(identifier="300", contact_info=contact_info, payment_info={})
    assert account
    assert account.status == CfsAccountStatus.PENDING.value
    assert account.payment_method == PaymentMethod.ONLINE_BANKING.value
    assert account.cfs_account is None
    assert account.cfs_party is None
    assert account.cfs_site is None


def test_get_payment_system_code(session):
    """Test get_payment_system_code."""
    assert online_banking_service.get_payment_system_code() == "PAYBC"


def test_get_payment_method_code(session):
    """Test get_payment_method_code."""
    assert online_banking_service.get_payment_method_code() == PaymentMethod.ONLINE_BANKING.value
