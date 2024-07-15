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

"""Tests to assure the EFT service layer.

Test-Suite to ensure that the EFT Service is working as expected.
"""

import pytest
from pay_api.exceptions import BusinessException
from pay_api.services.eft_service import EftService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from tests.utilities.base_test import factory_invoice, factory_payment_account


eft_service = EftService()


def test_get_payment_system_code(session):
    """Test get_payment_system_code."""
    code = eft_service.get_payment_system_code()
    assert code == 'PAYBC'


def test_get_payment_method_code(session):
    """Test get_payment_method_code."""
    code = eft_service.get_payment_method_code()
    assert code == 'EFT'


def test_has_no_payment_blockers(session):
    """Test for no payment blockers."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    payment_account.save()
    eft_service.ensure_no_payment_blockers(payment_account)
    assert True


def test_has_payment_blockers(session):
    """Test has payment blockers."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    payment_account.save()
    factory_invoice(payment_account, status_code=InvoiceStatus.OVERDUE.value).save()

    with pytest.raises(BusinessException):
        eft_service.ensure_no_payment_blockers(payment_account)
    assert True
