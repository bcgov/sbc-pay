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
from requests.exceptions import ConnectionError, ConnectTimeout, HTTPError

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.services.payment_service import PaymentService
from pay_api.utils.enums import Status
from tests.utilities.base_test import get_payment_request


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code: str = 'CP',
                            payment_system_code: str = 'PAYBC'):
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
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = Status.DRAFT.value
):
    """Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
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
    payment_response = PaymentService.create_payment(get_payment_request(), 'test')
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC')
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get('id') is not None
    # Create another payment with same request, the account should be the same
    PaymentService.create_payment(get_payment_request(), 'test')
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC')
    assert account_id == account_model.id


def test_create_payment_record_rollback(session):
    """Assert that the payment records are created."""
    # Mock here that the invoice update fails here to test the rollback scenario
    with patch('pay_api.services.invoice.Invoice.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(get_payment_request(), 'test')
        assert excinfo.type == Exception

    with patch('pay_api.services.payment.Payment.create', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(get_payment_request(), 'test')
        assert excinfo.type == Exception
    with patch('pay_api.services.paybc_service.PaybcService.create_invoice', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(get_payment_request(), 'test')
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

    payment_response = PaymentService.update_payment(payment.id, get_payment_request(), 'test')
    assert payment_response.get('id') is not None


def test_update_payment_record_transaction_invalid(session):
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

    payment_response = PaymentService.update_payment(payment.id, get_payment_request(), 'test')
    assert payment_response.get('id') is not None


def test_update_payment_completed_invalid(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.payment_status_code = Status.COMPLETED.value
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentService.update_payment(payment.id, get_payment_request(), 'test')
    assert excinfo.type == BusinessException


def test_update_payment_cancel_invalid(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.payment_status_code = Status.CANCELLED.value
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentService.update_payment(payment.id, get_payment_request(), 'test')
    assert excinfo.type == BusinessException


def test_update_payment_invoice_cancel_invalid(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.invoice_status_code = Status.CANCELLED.value
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_response = PaymentService.update_payment(payment.id, get_payment_request(), 'test')
    assert payment_response.get('id') is not None


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

    # Mock here that the invoice update fails here to test the rollback scenario
    with patch(
            'pay_api.services.payment_transaction.PaymentTransaction.find_active_by_payment_id',
            side_effect=Exception('mocked error'),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    with patch(
            'pay_api.services.payment_transaction.PaymentTransaction.update_transaction',
            side_effect=Exception('mocked error'),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    with patch('pay_api.services.payment.Payment.find_by_id', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    with patch('pay_api.services.payment_line_item.PaymentLineItem.create', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.paybc_service.PaybcService.update_invoice', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.invoice.Invoice.find_by_id', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.invoice.Invoice.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.payment.Payment.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), 'test')
        assert excinfo.type == Exception


def test_create_payment_record_rollback_on_paybc_connection_error(session):
    """Assert that the payment records are not created."""
    from unittest.mock import Mock
    # Mock here that the invoice update fails here to test the rollback scenario
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        with pytest.raises(ServiceUnavailableException) as excinfo:
            PaymentService.create_payment(get_payment_request(), 'test')
        assert excinfo.type == ServiceUnavailableException
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectTimeout('mocked error')):
        with pytest.raises(ServiceUnavailableException) as excinfo:
            PaymentService.create_payment(get_payment_request(), 'test')
        assert excinfo.type == ServiceUnavailableException

    mock_create_site = patch('pay_api.services.oauth_service.requests.post')

    mock_post = mock_create_site.start()
    mock_post.return_value = Mock(status_code=503)

    with patch('pay_api.services.oauth_service.requests.post', side_effect=HTTPError('mocked error')) as post_mock:
        post_mock.status_Code = 503
        with pytest.raises(HTTPError) as excinfo:
            PaymentService.create_payment(get_payment_request(), 'test')
        assert excinfo.type == HTTPError
