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

"""Tests to assure the Payment Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""

from unittest.mock import patch

import pytest

from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel
from pay_api.services.payment_service import PaymentService


def test_create_payment_record(session):
    """Assert that the payment records are created."""
    payment_request = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    payment_response = PaymentService.create_payment(payment_request, 'test')
    account_model = PaymentAccountModel.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC')
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get('id') is not None
    # Create another payment with same request, the account should be the same
    PaymentService.create_payment(payment_request, 'test')
    account_model = PaymentAccountModel.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC')
    assert account_id == account_model.id


def test_create_payment_record_rollback(session):
    """Assert that the payment records are created."""
    payment_request = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }

    # Mock here that the invoice update fails here to test the rollback scenario
    with patch('pay_api.services.invoice.Invoice.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(payment_request, 'test')
        assert excinfo.type == Exception

    with patch('pay_api.services.payment.Payment.create', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(payment_request, 'test')
        assert excinfo.type == Exception
    with patch('pay_api.services.paybc_service.PaybcService.create_invoice', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(payment_request, 'test')
        assert excinfo.type == Exception
