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
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import patch

import pytest
from faker import Faker
from flask import Flask
from freezegun import freeze_time
from pay_api.models import NonSufficientFunds as NonSufficientFundsModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.services import Statement as StatementService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import current_local_time

import config
from tasks.statement_task import StatementTask
from tasks.statement_due_task import StatementDueTask
from utils.enums import StatementNotificationAction
from utils.mailer import StatementNotificationInfo

from .factory import (
    factory_create_account, factory_invoice, factory_invoice_reference, factory_statement_recipient,
    factory_statement_settings)


fake = Faker()
app = None


# Travis Semple - in the future please remove this, this should be inside of conftest.py like the other fixtures.
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
                              payment_method_code=payment_method_code, status_code=InvoiceStatus.APPROVED.value,
                              total=invoice_total)
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
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

    return account, invoice, inv_ref, statement_recipient, statement_settings


# 1. EFT Invoice created between or on January 1st <-> January 31st
# 2. Statement Day February 1st
# 3. 7 day reminder Feb 21th (due date - 7)
# 4. Final reminder Feb 28th (due date client should be told to pay by this time)
# 5. Overdue Date and account locked March 15th
@pytest.mark.parametrize('test_name, action_on, action', [
    ('reminder', datetime(2023, 2, 21, 8), StatementNotificationAction.REMINDER),
    ('due', datetime(2023, 2, 28, 8), StatementNotificationAction.DUE),
    ('overdue', datetime(2023, 3, 15, 8), StatementNotificationAction.OVERDUE)
])
def test_send_unpaid_statement_notification(setup, session, test_name, action_on, action):
    """Assert payment reminder event is being sent."""
    account, invoice, _, \
        statement_recipient, _ = create_test_data(PaymentMethod.EFT.value,
                                                  datetime(2023, 1, 1, 8),  # Hour 0 doesnt work for CI
                                                  StatementFrequency.MONTHLY.value,
                                                  351.50)
    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert invoice.overdue_date
    assert account.payment_method == PaymentMethod.EFT.value

    # Generate statements runs at 8:01 UTC, currently set to 7:01 UTC, should be moved.
    with freeze_time(datetime(2023, 2, 1, 8, 0, 1)):
        StatementTask.generate_statements()

    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements) == 2  # items results and page total
    assert len(statements[0]) == 1  # items
    invoices = StatementInvoicesModel.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    summary = StatementService.get_summary(account.auth_account_id, statements[0][0].id)
    total_amount_owing = summary['total_due']

    with patch('utils.auth_event.AuthEvent.publish_lock_account_event') as mock_auth_event:
        with patch('tasks.statement_due_task.publish_payment_notification') as mock_mailer:
            with freeze_time(action_on):
                # Statement due task looks at the month before.
                StatementDueTask.process_unpaid_statements(statement_date_override=datetime(2023, 2, 1, 0))
                if action == StatementNotificationAction.OVERDUE:
                    mock_auth_event.assert_called()
                    assert statements[0][0].overdue_notification_date
                    assert NonSufficientFundsModel.find_by_invoice_id(invoice.id)
                    assert account.has_overdue_invoices
                else:
                    due_date = statements[0][0].to_date + relativedelta(months=1)
                    mock_mailer.assert_called_with(StatementNotificationInfo(auth_account_id=account.auth_account_id,
                                                                             statement=statements[0][0],
                                                                             action=action,
                                                                             due_date=due_date,
                                                                             emails=statement_recipient.email,
                                                                             total_amount_owing=total_amount_owing))


def test_unpaid_statement_notification_not_sent(setup, session):
    """Assert payment reminder event is not being sent."""
    # Assert notification was published to the mailer queue
    with patch('tasks.statement_due_task.publish_payment_notification') as mock_mailer:
        # Freeze time to 10th of the month - should not trigger any notification
        with freeze_time(current_local_time().replace(day=10)):
            StatementDueTask.process_unpaid_statements()
            mock_mailer.assert_not_called()


def test_overdue_invoices_updated(setup, session):
    """Assert invoices are transitioned to overdue status."""
    invoice_date = current_local_time() - relativedelta(months=2, days=15)
    account, invoice, _, \
        _, _ = create_test_data(PaymentMethod.EFT.value,
                                invoice_date,
                                StatementFrequency.MONTHLY.value,
                                351.50)
    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    invoice2 = factory_invoice(payment_account=account, created_on=current_local_time().date() + relativedelta(hours=1),
                               payment_method_code=PaymentMethod.EFT.value, status_code=InvoiceStatus.APPROVED.value,
                               total=10.50)

    assert invoice2.payment_method_code == PaymentMethod.EFT.value
    assert invoice2.invoice_status_code == InvoiceStatus.APPROVED.value
    assert account.payment_method == PaymentMethod.EFT.value

    StatementDueTask.process_unpaid_statements()
    assert invoice.invoice_status_code == InvoiceStatus.OVERDUE.value
    assert invoice2.invoice_status_code == InvoiceStatus.APPROVED.value
