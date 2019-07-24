
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

"""Tests to assure the UpdateStalePayment .
Test-Suite to ensure that the UpdateStalePayment is working as expected.
"""

import uuid
from datetime import datetime

import pytest

from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from update_stale_payment_records import update_transaction


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



def test_run(session):
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

    print("#$%@#%@#%@#$%@#$%$")
    update_transaction()