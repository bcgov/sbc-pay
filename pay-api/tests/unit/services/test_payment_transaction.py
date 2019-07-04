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

import uuid
from datetime import datetime

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.utils.enums import Status
from pay_api.utils.errors import Error


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


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='DRAFT'):
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
        invoice_status_code='DRAFT',
        account_id=account_id,
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
        line_item_status_code='CREATED',
    )


def factory_payment_transaction(
        payment_id: str,
        status_code: str = 'DRAFT',
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


def test_transaction_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment_transaction = PaymentTransactionService()
    payment_transaction.status_code = 'DRAFT'
    payment_transaction.transaction_end_time = datetime.now()
    payment_transaction.transaction_start_time = datetime.now()
    payment_transaction.pay_system_url = 'http://google.com'
    payment_transaction.client_system_url = 'http://google.com'
    payment_transaction.payment_id = payment.id
    payment_transaction = payment_transaction.save()

    transaction = PaymentTransactionService.find_by_id(payment.id, payment_transaction.id)

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None


def test_transaction_create_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create(payment.id, 'http://google.com/')

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.asdict() is not None


def test_transaction_create_from_invalid_payment(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.create(999, 'http://google.com/')
    assert excinfo.value.status == Error.PAY005.status
    assert excinfo.value.message == Error.PAY005.message
    assert excinfo.value.code == Error.PAY005.name


def test_transaction_update(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create(payment.id, 'http://google.com/')
    transaction = PaymentTransactionService.update_transaction(payment.id, transaction.id, '123451')

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == Status.COMPLETED.value


def test_transaction_update_with_no_receipt(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create(payment.id, 'http://google.com/')
    transaction = PaymentTransactionService.update_transaction(payment.id, transaction.id, None)

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == Status.FAILED.value
    assert transaction.asdict() is not None


def test_transaction_update_completed(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create(payment.id, 'http://google.com/')
    transaction = PaymentTransactionService.update_transaction(payment.id, transaction.id, '123451')

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.update_transaction(payment.id, transaction.id, '123451')
    assert excinfo.value.status == Error.PAY006.status
    assert excinfo.value.message == Error.PAY006.message
    assert excinfo.value.code == Error.PAY006.name


def test_transaction_create_new_on_completed_payment(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create(payment.id, 'http://google.com/')
    PaymentTransactionService.update_transaction(payment.id, transaction.id, '123451')

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.create(payment.id, 'http://google.com/')
    assert excinfo.value.status == Error.PAY006.status
    assert excinfo.value.message == Error.PAY006.message
    assert excinfo.value.code == Error.PAY006.name


def test_multiple_transactions_for_single_payment(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    PaymentTransactionService.create(payment.id, 'http://google.com/')
    PaymentTransactionService.create(payment.id, 'http://google.com/')
    transaction = PaymentTransactionService.create(payment.id, 'http://google.com/')

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.status_code == Status.CREATED.value


def test_transaction_invalid_lookup(session):
    """Invalid lookup.."""
    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.find_by_id(1, uuid.uuid4())
    assert excinfo.value.status == Error.PAY008.status
    assert excinfo.value.message == Error.PAY008.message
    assert excinfo.value.code == Error.PAY008.name


def test_transaction_invalid_update(session):
    """Invalid update.."""
    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.update_transaction(1, uuid.uuid4(), None)
    assert excinfo.value.status == Error.PAY008.status
    assert excinfo.value.message == Error.PAY008.message
    assert excinfo.value.code == Error.PAY008.name


def test_transaction_find_active_lookup(session):
    """Invalid lookup.."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id, Status.CREATED.value)
    transaction.save()

    transaction = PaymentTransactionService.find_active_by_payment_id(payment.id)
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.status_code == Status.CREATED.value


def test_transaction_find_active_none_lookup(session):
    """Invalid lookup.."""
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

    transaction = PaymentTransactionService.find_active_by_payment_id(payment.id)
    assert transaction is None


def test_transaction_find_by_payment_id(session):
    """Find all transactions by payment id.."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id, Status.CREATED.value)
    transaction.save()

    transaction = PaymentTransactionService.find_by_payment_id(payment.id)
    assert transaction is not None
    assert transaction.get('items') is not None
    assert transaction.get('items')[0].get('_links') is not None


def test_no_existing_transaction(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.find_active_by_payment_id(payment.id)

    assert transaction is None
