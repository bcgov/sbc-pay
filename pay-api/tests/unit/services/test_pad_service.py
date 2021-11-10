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

"""Tests to assure the PAD Banking service layer.

Test-Suite to ensure that the PAD Banking layer is working as expected.
"""

from pay_api.services.pad_service import PadService


pad_service = PadService()


def test_create_account(session):
    """Test create_account."""
    payment_info = {
        'bankInstitutionNumber': 111,
        'bankTransitNumber': 222,
        'bankAccountNumber': 33333333
    }
    account = pad_service.create_account(identifier='100', contact_info={}, payment_info=payment_info)
    assert account
    assert account.bank_number == payment_info.get('bankInstitutionNumber')


def test_get_payment_system_code(session):
    """Test get_payment_system_code."""
    code = pad_service.get_payment_system_code()
    assert code == 'PAYBC'


def test_get_payment_method_code(session):
    """Test get_payment_method_code."""
    code = pad_service.get_payment_method_code()
    assert code == 'PAD'
