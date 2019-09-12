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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""
from datetime import datetime, timedelta

from pay_api.models import Invoice, Payment, PaymentAccount
from pay_api.models.payment_transaction import PaymentTransaction


def factory_payment_account(corp_number: str = 'CP0001234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='DRAFT'):
    """Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str):
    """Factory."""
    return Invoice(payment_id=payment_id,
                   invoice_status_code='DRAFT',
                   account_id=account_id,
                   total=0, created_by='test', created_on=datetime.now())


def factory_payment_transaction(payment_id: str, status_code: str = 'DRAFT', redirect_url: str = 'http://google.com/',
                                pay_system_url: str = 'http://google.com',
                                transaction_start_time: datetime = datetime.now(),
                                transaction_end_time: datetime = datetime.now()):
    """Factory."""
    return PaymentTransaction(payment_id=payment_id,
                              status_code=status_code,
                              client_system_url=redirect_url,
                              pay_system_url=pay_system_url,
                              transaction_start_time=transaction_start_time,
                              transaction_end_time=transaction_end_time)


def test_payment_transaction(session):
    """Assert a payment_transaction is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    invoice.save()
    payment_transaction = factory_payment_transaction(payment_id=payment.id)
    payment_transaction.save()
    assert payment_transaction.id is not None


def test_find_older_records(session):
    """Assert a payment_transaction is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    invoice.save()

    payment_transaction_now = factory_payment_transaction(payment_id=payment.id)
    payment_transaction_now.save()

    payment_transaction_100_days_old = factory_payment_transaction(
        payment_id=payment.id,
        transaction_start_time=datetime.now() - timedelta(days=100))
    payment_transaction_100_days_old.save()

    payment_transaction_3_hours_old = factory_payment_transaction(
        payment_id=payment.id,
        transaction_start_time=datetime.now() - timedelta(
            hours=3))

    payment_transaction_3_hours_old.save()

    payment_transaction_1_hour_old = factory_payment_transaction(
        payment_id=payment.id,
        transaction_start_time=datetime.now() - timedelta(
            hours=1))
    payment_transaction_1_hour_old.save()

    payment_transaction_2_hours_old = factory_payment_transaction(
        payment_id=payment.id,
        transaction_start_time=datetime.now() - timedelta(
            hours=2))
    payment_transaction_2_hours_old.save()

    all_records = payment_transaction_now.find_stale_records(hours=2,
                                                             minutes=10)  # find records which are 2.10 hours older
    assert len(all_records) == 2
    for record in all_records:
        assert record.transaction_start_time < datetime.now() - timedelta(hours=2)


def test_find_older_records_invalid_status(session):
    """Assert a payment_transaction is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    invoice.save()

    payment_transaction_now = factory_payment_transaction(payment_id=payment.id, status_code='COMPLETED')
    payment_transaction_now.save()  # not eligible

    payment_transaction_now_draft = factory_payment_transaction(payment_id=payment.id, status_code='DRAFT')
    payment_transaction_now_draft.save()  # not eligible

    payment_transaction_now_draft_3_hours = factory_payment_transaction(
        payment_id=payment.id, status_code='DRAFT',
        transaction_start_time=datetime.now() - timedelta(
            hours=3))
    payment_transaction_now_draft_3_hours.save()  # this is eligible

    payment_transaction_now_draft_completed_3_hours = factory_payment_transaction(
        payment_id=payment.id,
        status_code='COMPLETED',
        transaction_start_time=datetime.now() - timedelta(
            hours=3))
    payment_transaction_now_draft_completed_3_hours.save()  # not eligible

    all_records = payment_transaction_now.find_stale_records(hours=2,
                                                             minutes=59)  # find records which are 2.59 hourolder
    assert len(all_records) == 1
