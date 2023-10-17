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

"""Tests to assure the UnpaidStatementNotifyTask.

Test-Suite to ensure that the UnpaidStatementNotifyTask is working as expected.
"""
import decimal
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from faker import Faker
from flask import Flask
from freezegun import freeze_time
from pay_api.models import Statement, StatementInvoices
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import get_first_and_last_dates_of_month, get_previous_month_and_year

import config
from tasks.statement_task import StatementTask
from tasks.unpaid_statement_notify_task import UnpaidStatementNotifyTask

from .factory import (
    factory_create_account, factory_invoice, factory_invoice_reference, factory_payment, factory_statement_recipient,
    factory_statement_settings)


fake = Faker()
app = None


@pytest.fixture
def setup():
    """Initialize app with test env for testing."""
    global app
    app = Flask(__name__)
    app.env = 'testing'
    app.config.from_object(config.CONFIGURATION['testing'])


def create_test_data(payment_method_code: str, payment_date: datetime,
                     statement_frequency: str, invoice_total: decimal = 0.00,
                     invoice_paid: decimal = 0.00):
    """Create seed data for tests."""
    account = factory_create_account(auth_account_id='1', payment_method_code=payment_method_code)
    invoice = factory_invoice(payment_account=account, created_on=payment_date,
                              payment_method_code=payment_method_code, status_code=InvoiceStatus.OVERDUE.value,
                              total=invoice_total)
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    payment = factory_payment(payment_date=payment_date, invoice_number=inv_ref.invoice_number)
    statement_recipient = factory_statement_recipient(auth_user_id=account.auth_account_id,
                                                      first_name=fake.first_name(),
                                                      last_name=fake.last_name(),
                                                      email=fake.email(),
                                                      payment_account_id=account.id)

    statement_settings = factory_statement_settings(
        pay_account_id=account.id,
        from_date=payment_date,
        frequency=statement_frequency
    )

    return account, invoice, inv_ref, payment, statement_recipient, statement_settings


def test_send_unpaid_statement_notification(setup, session):
    """Assert payment reminder event is being sent."""
    last_month, last_year = get_previous_month_and_year()
    previous_month_year = datetime(last_year, last_month, 5)

    account, invoice, inv_ref, payment, \
        statement_recipient, statement_settings = create_test_data(PaymentMethod.EFT.value,
                                                                   previous_month_year,
                                                                   StatementFrequency.MONTHLY.value,
                                                                   351.50)

    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert account.payment_method == PaymentMethod.EFT.value

    now = datetime.now()
    _, last_day = get_first_and_last_dates_of_month(now.month, now.year)

    # Generate statement for previous month - freeze time to the 1st of the current month
    with freeze_time(datetime.now().replace(day=1)):
        StatementTask.generate_statements()

    # Assert statements and invoice was created
    statements = Statement.find_all_statements_for_account(auth_account_id=account.auth_account_id, page=1,
                                                           limit=100)
    assert statements is not None
    assert len(statements) == 2  # items results and page total
    assert len(statements[0]) == 1  # items
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    with app.app_context():
        # Assert notification was published to the mailer queue
        with patch('tasks.unpaid_statement_notify_task.publish_payment_notification') as mock_mailer:
            with patch('tasks.unpaid_statement_notify_task.get_token') as mock_get_token:
                # Freeze time to due date - trigger due notification
                with freeze_time(last_day):
                    mock_get_token.return_value = 'mock_token'
                    UnpaidStatementNotifyTask.notify_unpaid_statements()
                    mock_get_token.assert_called()
                    mock_mailer.assert_called_with(pay_account=account,
                                                   statement=statements[0][0],
                                                   is_due=True,
                                                   due_date=last_day.date(),
                                                   emails=statement_recipient.email)

                # Freeze time to due date - trigger reminder notification
                with freeze_time(last_day - timedelta(days=7)):
                    mock_get_token.return_value = 'mock_token'
                    UnpaidStatementNotifyTask.notify_unpaid_statements()
                    mock_get_token.assert_called()
                    mock_mailer.assert_called_with(pay_account=account,
                                                   statement=statements[0][0],
                                                   is_due=False,
                                                   due_date=last_day.date(),
                                                   emails=statement_recipient.email)


def test_unpaid_statement_notification_not_sent(setup, session):
    """Assert payment reminder event is not being sent."""
    with app.app_context():
        # Assert notification was published to the mailer queue
        with patch('tasks.unpaid_statement_notify_task.publish_payment_notification') as mock_mailer:
            # Freeze time to 10th of the month - should not trigger any notification
            with freeze_time(datetime.now().replace(day=10)):
                UnpaidStatementNotifyTask.notify_unpaid_statements()
                mock_mailer.assert_not_called()
