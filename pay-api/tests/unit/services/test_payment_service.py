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

from datetime import datetime
from unittest.mock import patch

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.services.payment_service import PaymentService
from pay_api.utils.enums import Status


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(
        corp_number=corp_number,
        corp_type_code=corp_type_code,
        payment_system_code=payment_system_code,
        party_number='11111',
        account_number='4101',
        site_number='29921',
    )


def factory_payment(
    payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code=Status.DRAFT.value
):
    """Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        paid=0,
        created_by='test',
        created_on=datetime.now(),
    )


def factory_invoice(payment_id: str, account_id: str):
    """Factory."""
    return Invoice(
        payment_id=payment_id,
        invoice_status_code=Status.DRAFT.value,
        account_id=account_id,
        invoice_number=10021,
        total=0,
        created_by='test',
        created_on=datetime.now(),
    )


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10):
    """Factory."""
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        line_item_status_code=Status.CREATED.value,
    )


def factory_payment_transaction(
    payment_id: str,
    status_code: str = Status.DRAFT.value,
    client_system_url: str = 'http://google.com/',
    pay_system_url: str = 'http://google.com',
    transaction_start_time: datetime = datetime.now(),
    transaction_end_time: datetime = datetime.now(),
):
    """Factory."""
    return PaymentTransaction(
        payment_id=payment_id,
        status_code=status_code,
        client_system_url=client_system_url,
        pay_system_url=pay_system_url,
        transaction_start_time=transaction_start_time,
        transaction_end_time=transaction_end_time,
    )


def test_create_payment_record(session):
    """Assert that the payment records are created."""
    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
    }
    payment_response = PaymentService.create_payment(payment_request, 'test')
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC')
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get('id') is not None
    # Create another payment with same request, the account should be the same
    PaymentService.create_payment(payment_request, 'test')
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC')
    assert account_id == account_model.id


def test_create_payment_record_rollback(session):
    """Assert that the payment records are created."""
    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
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


def test_update_payment_record(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
    }

    payment_response = PaymentService.update_payment(payment.id, payment_request, 'test')

    assert payment_response.get('id') is not None


def test_update_payment_record_transaction_completed(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id, Status.COMPLETED.value)
    transaction.save()

    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
    }

    with pytest.raises(BusinessException) as excinfo:
        PaymentService.update_payment(payment.id, payment_request, 'test')
    assert excinfo.type == BusinessException


def test_update_payment_record_rollback(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
    }

    # Mock here that the invoice update fails here to test the rollback scenario
    with patch(
        'pay_api.services.payment_transaction.PaymentTransaction.find_active_by_payment_id',
        side_effect=Exception('mocked error'),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    with patch(
        'pay_api.services.payment_transaction.PaymentTransaction.update_transaction',
        side_effect=Exception('mocked error'),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    with patch('pay_api.services.payment.Payment.find_by_id', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    with patch('pay_api.services.payment_line_item.PaymentLineItem.create', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.paybc_service.PaybcService.update_invoice', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.invoice.Invoice.find_by_id', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.invoice.Invoice.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.payment.Payment.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, payment_request, 'test')
        assert excinfo.type == Exception
