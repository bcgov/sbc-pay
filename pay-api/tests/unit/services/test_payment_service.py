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
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account, factory_payment_line_item,
    factory_payment_transaction, get_payment_request, get_zero_dollar_payment_request)

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.services.payment_service import PaymentService
from pay_api.utils.enums import Status


test_user_token = {'preferred_username': 'test'}


def test_create_payment_record(session):
    """Assert that the payment records are created."""
    payment_response = PaymentService.create_payment(get_payment_request(), test_user_token)
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP0001234', 'CP', 'PAYBC')
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get('id') is not None
    # Create another payment with same request, the account should be the same
    PaymentService.create_payment(get_payment_request(), test_user_token)
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP0001234', 'CP', 'PAYBC')
    assert account_id == account_model.id


def test_create_payment_record_rollback(session):
    """Assert that the payment records are created."""
    # Mock here that the invoice update fails here to test the rollback scenario
    with patch('pay_api.services.invoice.Invoice.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(get_payment_request(), test_user_token)
        assert excinfo.type == Exception

    with patch('pay_api.services.payment.Payment.create', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(get_payment_request(), test_user_token)
        assert excinfo.type == Exception
    with patch('pay_api.services.paybc_service.PaybcService.create_invoice', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_payment(get_payment_request(), test_user_token)
        assert excinfo.type == Exception


def test_update_payment_record(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_response = PaymentService.update_payment(payment.id, get_payment_request(), {})
    assert payment_response.get('id') is not None


def test_update_payment_record_transaction_invalid(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id, Status.COMPLETED.value)
    transaction.save()

    payment_response = PaymentService.update_payment(payment.id, get_payment_request(), {})
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
    factory_invoice_reference(invoice.id).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentService.update_payment(payment.id, get_payment_request(), {})
    assert excinfo.type == BusinessException


def test_update_payment_deleted_invalid(session):
    """Assert that the payment records are not updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.payment_status_code = Status.DELETED.value
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentService.update_payment(payment.id, get_payment_request(), {})
    assert excinfo.type == BusinessException


def test_update_payment_invoice_deleted_invalid(session):
    """Assert that the payment records are not updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.invoice_status_code = Status.DELETED.value
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_response = PaymentService.update_payment(payment.id, get_payment_request(), {})
    assert payment_response.get('id') is not None


def test_update_payment_record_rollback(session):
    """Assert that the payment records are updated."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

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
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    with patch(
            'pay_api.services.payment_transaction.PaymentTransaction.update_transaction',
            side_effect=Exception('mocked error'),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    with patch('pay_api.services.payment.Payment.find_by_id', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    with patch('pay_api.services.payment_line_item.PaymentLineItem.create', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.paybc_service.PaybcService.update_invoice', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.invoice.Invoice.find_by_id', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.invoice.Invoice.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception

    # reset transaction
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with patch('pay_api.services.payment.Payment.save', side_effect=Exception('mocked error')):
        with pytest.raises(Exception) as excinfo:
            PaymentService.update_payment(payment.id, get_payment_request(), {})
        assert excinfo.type == Exception


def test_create_payment_record_rollback_on_paybc_connection_error(session):
    """Assert that the payment records are not created."""
    # Mock here that the invoice update fails here to test the rollback scenario
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        with pytest.raises(ServiceUnavailableException) as excinfo:
            PaymentService.create_payment(get_payment_request(), test_user_token)
        assert excinfo.type == ServiceUnavailableException

    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectTimeout('mocked error')):
        with pytest.raises(ServiceUnavailableException) as excinfo:
            PaymentService.create_payment(get_payment_request(), test_user_token)
        assert excinfo.type == ServiceUnavailableException

    with patch('pay_api.services.oauth_service.requests.post', side_effect=HTTPError('mocked error')) as post_mock:
        post_mock.status_Code = 503
        with pytest.raises(HTTPError) as excinfo:
            PaymentService.create_payment(get_payment_request(), test_user_token)
        assert excinfo.type == HTTPError


def test_create_zero_dollar_payment_record(session):
    """Assert that the payment records are created and completed."""
    payment_response = PaymentService.create_payment(get_zero_dollar_payment_request(), test_user_token)
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP0001234', 'CP', 'INTERNAL')
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get('id') is not None
    assert payment_response.get('status_code') == 'COMPLETED'
    # Create another payment with same request, the account should be the same
    PaymentService.create_payment(get_zero_dollar_payment_request(), test_user_token)
    account_model = PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP0001234', 'CP', 'INTERNAL')
    assert account_id == account_model.id
    assert payment_response.get('status_code') == 'COMPLETED'


def test_delete_payment(session, auth_mock):
    """Assert that the payment records are soft deleted."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    PaymentService.delete_payment(payment.id)
    payment = Payment.find_by_id(payment.id)
    assert payment.payment_status_code == Status.DELETED.value
    assert payment.invoices[0].invoice_status_code == Status.DELETED.value


def test_delete_completed_payment(session, auth_mock):
    """Assert that the payment records are soft deleted."""
    payment_account = factory_payment_account()
    payment = factory_payment(payment_status_code=Status.COMPLETED.value)
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with pytest.raises(Exception) as excinfo:
        PaymentService.delete_payment(payment.id)
    assert excinfo.type == BusinessException
