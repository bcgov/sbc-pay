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

"""Tests to assure the CreateInvoiceTask.

Test-Suite to ensure that the CreateInvoiceTask is working as expected.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from flask import current_app
from freezegun import freeze_time

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod
from tasks.unpaid_invoice_notify_task import UnpaidInvoiceNotifyTask
from utils import mailer

from .factory import factory_create_online_banking_account, factory_create_pad_account, factory_invoice


def test_unpaid_one_invoice(session):
    """Assert events are being sent."""
    # Create an account and an invoice for the account
    account = factory_create_online_banking_account(
        auth_account_id="1", status=CfsAccountStatus.ACTIVE.value, cfs_account="1111"
    )
    # Create an invoice for this account
    cfs_account = CfsAccountModel.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)

    invoice = factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=10,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    # invoke today ;no mail
    with patch.object(mailer, "publish_mailer_events") as mock_mailer:
        UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
        mock_mailer.assert_not_called()

    time_delay = current_app.config["NOTIFY_AFTER_DAYS"]

    # invoke one day before the time delay ;shud be no mail
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=(time_delay - 1))
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            mock_mailer.assert_not_called()

    # exact day , mail shud be invoked
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            mock_mailer.assert_called()

    # after the time delay day ;shud not get sent
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay + 1)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            mock_mailer.assert_not_called()


def test_unpaid_multiple_invoice(session):
    """Assert events are being sent."""
    # Create an account and an invoice for the account
    account = factory_create_online_banking_account(
        auth_account_id="1", status=CfsAccountStatus.ACTIVE.value, cfs_account="1111"
    )
    # Create an invoice for this account
    cfs_account = CfsAccountModel.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)

    invoice = factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=10,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=200,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )

    previous_day = datetime.now(tz=UTC) - timedelta(days=1)
    factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=2000,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )

    # created two invoices ; so two events
    time_delay = current_app.config["NOTIFY_AFTER_DAYS"]
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            assert mock_mailer.call_count == 1

    # created one invoice yesterday ; so assert one
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay - 1)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            assert mock_mailer.call_count == 1


def test_unpaid_invoice_pad(session):
    """Assert events are being sent."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    # Create an invoice for this account
    cfs_account = CfsAccountModel.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)

    invoice = factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=10,
        cfs_account_id=cfs_account.id,
    )
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    # invoke today ;no mail
    time_delay = current_app.config["NOTIFY_AFTER_DAYS"]
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            mock_mailer.assert_not_called()


def test_unpaid_single_invoice_total(session):
    """Assert events are being sent."""
    # Create an account and an invoice for the account
    account = factory_create_online_banking_account(
        auth_account_id="1", status=CfsAccountStatus.ACTIVE.value, cfs_account="1111"
    )
    # Create an invoice for this account
    cfs_account = CfsAccountModel.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)
    # invoice amount
    total_invoice1 = 100
    total_invoice2 = 200

    invoice = factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=total_invoice1,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    previous_day = datetime.now(tz=UTC) - timedelta(days=1)
    factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=total_invoice2,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )

    # created two invoices ; so two events
    time_delay = current_app.config["NOTIFY_AFTER_DAYS"]
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            assert mock_mailer.call_args.args[2].get("transactionAmount") == total_invoice1 + total_invoice2

    # created one invoice yesterday ; so assert one
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay - 1)
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            assert mock_mailer.call_count == 1
            assert mock_mailer.call_args.args[2].get("transactionAmount") == total_invoice1 + total_invoice2


def test_unpaid_multiple_invoice_total(session):
    """Assert events are being sent."""
    # Create an account and an invoice for the account
    account = factory_create_online_banking_account(
        auth_account_id="1", status=CfsAccountStatus.ACTIVE.value, cfs_account="1111"
    )
    # Create an invoice for this account
    cfs_account = CfsAccountModel.find_effective_by_payment_method(account.id, PaymentMethod.ONLINE_BANKING.value)
    # invoice amount
    total_invoice1 = 100
    total_invoice2 = 200
    total_invoice3 = 300

    invoice = factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=total_invoice1,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC),
        total=total_invoice2,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )

    # this is future invoice
    factory_invoice(
        payment_account=account,
        created_on=datetime.now(tz=UTC) + timedelta(days=1),
        total=total_invoice3,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        cfs_account_id=cfs_account.id,
    )

    # created two invoices ; so two events
    time_delay = current_app.config["NOTIFY_AFTER_DAYS"]
    day_after_time_delay = datetime.now(tz=UTC) + timedelta(days=time_delay)
    total_amount = total_invoice1 + total_invoice2 + total_invoice3
    # total amount is the same for any day invocation
    with freeze_time(day_after_time_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            assert mock_mailer.call_count == 1
            assert mock_mailer.call_args.args[2].get("transactionAmount") == total_amount

    one_more_day_delay = datetime.now(tz=UTC) + timedelta(days=time_delay + 1)
    with freeze_time(one_more_day_delay):
        with patch.object(mailer, "publish_mailer_events") as mock_mailer:
            UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            assert mock_mailer.call_count == 1
            assert mock_mailer.call_args.args[2].get("transactionAmount") == total_amount
