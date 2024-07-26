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

from unittest.mock import MagicMock, patch
import pytest
from pay_api.exceptions import BusinessException
from pay_api.services.eft_service import EftService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from pay_api.utils.errors import Error
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


def test_refund_eft_credits(session):
    """Test the _refund_eft_credits method."""
    credit1 = MagicMock(remaining_amount=2)
    credit2 = MagicMock(remaining_amount=4)
    credit3 = MagicMock(remaining_amount=3)

    with patch('pay_api.services.eft_service.EFTShortnames.get_eft_credits',
               return_value=[credit1, credit2, credit3]), \
         patch('pay_api.services.eft_service.EFTShortnames.get_eft_credit_balance', return_value=9):
        EftService._refund_eft_credits(1, '8')
        assert credit1.remaining_amount == 0
        assert credit2.remaining_amount == 0
        assert credit3.remaining_amount == 1

        credit1.remaining_amount = 5
        credit2.remaining_amount = 5

        with patch('pay_api.services.eft_service.EFTShortnames.get_eft_credit_balance', return_value=10):
            EftService._refund_eft_credits(1, '7')
            assert credit1.remaining_amount == 0
            assert credit2.remaining_amount == 3

        credit1.remaining_amount = 5
        credit2.remaining_amount = 2

        with patch('pay_api.services.eft_service.EFTShortnames.get_eft_credit_balance', return_value=7):
            EftService._refund_eft_credits(1, '1')
            assert credit1.remaining_amount == 4
            assert credit2.remaining_amount == 2


def test_refund_eft_credits_exceed_balance(session):
    """Test refund amount exceeds eft_credit_balance."""
    credit1 = MagicMock(remaining_amount=2)
    credit2 = MagicMock(remaining_amount=4)
    credit3 = MagicMock(remaining_amount=3)

    with patch('pay_api.services.eft_service.EFTShortnames.get_eft_credits',
               return_value=[credit1, credit2, credit3]), \
         patch('pay_api.services.eft_service.EFTShortnames.get_eft_credit_balance', return_value=8), \
         patch('flask.current_app.logger.error') as mock_error_logger:

        with pytest.raises(BusinessException) as excinfo:
            EftService._refund_eft_credits(1, '20')

        assert excinfo.value.code == Error.INVALID_TRANSACTION.name
        mock_error_logger.assert_called_with('Shortname 1 Refund amount exceed eft_credits remaining amount.')
