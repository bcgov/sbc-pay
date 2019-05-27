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

from datetime import datetime

from pay_api.models import Payment, PaymentAccount, Invoice, PaymentLineItem, FeeSchedule, PaymentTransaction
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='DRAFT',
                    total: int = 0):
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, total=total, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str):
    return Invoice(payment_id=payment_id,
                   invoice_status_code='DRAFT',
                   account_id=account_id,
                   total=0, created_by='test', created_on=datetime.now())


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10):
    return PaymentLineItem(invoice_id=invoice_id,
                           fee_schedule_id=fee_schedule_id,
                           filing_fees=filing_fees,
                           total=total)


def factory_payment_transaction(payment_id: str, status_code: str = 'DRAFT', redirect_url: str = 'http://google.com/',
                                pay_system_url: str = 'http://google.com',
                                transaction_start_time: datetime = datetime.now(),
                                transaction_end_time: datetime = datetime.now()):
    return PaymentTransaction(payment_id=payment_id,
                              status_code=status_code,
                              redirect_url=redirect_url,
                              pay_system_url=pay_system_url,
                              transaction_start_time=transaction_start_time,
                              transaction_end_time=transaction_end_time)


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
    payment_transaction.redirect_url = 'http://google.com'
    payment_transaction.payment_id = payment.id
    payment_transaction = payment_transaction.save()

    transaction = PaymentTransactionService.find_by_id(payment_transaction.id)

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.redirect_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None


def test_transaction_invalid_lookup(session):
    p = PaymentTransactionService.find_by_id(999)

    assert p is not None
    assert p.id is None
