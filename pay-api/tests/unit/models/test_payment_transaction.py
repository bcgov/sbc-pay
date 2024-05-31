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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""
from datetime import datetime, timedelta

from tests.utilities.base_test import (
    factory_invoice, factory_payment, factory_payment_account, factory_payment_transaction)


def test_payment_transaction(session):
    """Assert a payment_transaction is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account=payment_account)
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
    invoice = factory_invoice(payment_account=payment_account)
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
    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()

    payment_transaction_now = factory_payment_transaction(payment_id=payment.id, status_code='COMPLETED')
    payment_transaction_now.save()  # not eligible

    payment_transaction_now_draft = factory_payment_transaction(payment_id=payment.id, status_code='CREATED')
    payment_transaction_now_draft.save()  # not eligible

    payment_transaction_now_draft_3_hours = factory_payment_transaction(
        payment_id=payment.id, status_code='CREATED',
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
