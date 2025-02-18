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

"""Tests to assure the StatementNotificationTask.

Test-Suite to ensure that the StatementNotificationTask is working as expected.
"""
import decimal
from datetime import datetime, timezone
from unittest.mock import ANY, patch

import pytest
from faker import Faker
from flask import Flask
from freezegun import freeze_time
from pay_api.models import Statement, StatementInvoices
from pay_api.services import Statement as StatementService
from pay_api.utils.enums import InvoiceStatus, NotificationStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import get_previous_month_and_year

import config
from tasks.statement_notification_task import StatementNotificationTask
from tasks.statement_task import StatementTask
from tests.jobs.factory import (
    factory_create_account,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_statement_recipient,
    factory_statement_settings,
)

fake = Faker()
app = None


@pytest.fixture
def setup():
    """Initialize app with test env for testing."""
    global app
    app = Flask(__name__)
    app.env = "testing"
    app.config.from_object(config.CONFIGURATION["testing"])


def create_test_data(
    payment_method_code: str,
    payment_date: datetime,
    statement_frequency: str,
    invoice_total: decimal = 0.00,
    invoice_paid: decimal = 0.00,
):
    """Create seed data for tests."""
    account = factory_create_account(auth_account_id="1", payment_method_code=payment_method_code)
    invoice = factory_invoice(
        payment_account=account,
        created_on=payment_date,
        payment_method_code=payment_method_code,
        status_code=InvoiceStatus.OVERDUE.value,
        total=invoice_total,
    )
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    payment = factory_payment(payment_date=payment_date, invoice_number=inv_ref.invoice_number)
    statement_recipient = factory_statement_recipient(
        auth_user_id=account.auth_account_id,
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        email=fake.email(),
        payment_account_id=account.id,
    )

    statement_settings = factory_statement_settings(
        pay_account_id=account.id, from_date=payment_date, frequency=statement_frequency
    )

    return account, invoice, inv_ref, payment, statement_recipient, statement_settings


def test_send_notifications(session):
    """Test invoke send statement notifications."""
    StatementNotificationTask.send_notifications()
    assert True


@pytest.mark.parametrize(
    "payment_method_code",
    [
        PaymentMethod.CASH.value,
        PaymentMethod.CC.value,
        PaymentMethod.DRAWDOWN.value,
        PaymentMethod.EJV.value,
        PaymentMethod.INTERNAL.value,
        PaymentMethod.ONLINE_BANKING.value,
        PaymentMethod.PAD.value,
    ],
)
def test_send_monthly_notifications(setup, session, payment_method_code):  # pylint: disable=unused-argument
    """Test send monthly statement notifications."""
    # create statement, invoice, payment data for previous month
    last_month, last_year = get_previous_month_and_year()
    previous_month_year = datetime(last_year, last_month, 5)

    account, invoice, inv_ref, payment, statement_recipient, statement_settings = create_test_data(
        payment_method_code, previous_month_year, StatementFrequency.MONTHLY.value
    )

    assert invoice.payment_method_code == payment_method_code
    assert account.payment_method == payment_method_code

    # Generate statement for previous month - freeze time to the 1st of the current month
    with freeze_time(datetime.now(tz=timezone.utc).replace(day=1, hour=8)):
        StatementTask.generate_statements()

    # Assert statements and invoice was created
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements) == 2  # items results and page total
    assert len(statements[0]) == 1  # items
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Assert notification send_email was invoked
    with patch.object(StatementNotificationTask, "send_email", return_value=True) as mock_mailer:
        with patch("tasks.statement_notification_task.get_token") as mock_get_token:
            mock_get_token.return_value = "mock_token"
            StatementNotificationTask.send_notifications()
            mock_get_token.assert_called_once()
            # Assert token and email recipient - mock any for HTML generated
            mock_mailer.assert_called_with(mock_get_token.return_value, statement_recipient.email, ANY)

    # Assert statement notification code indicates success
    statement: Statement = Statement.find_by_id(statements[0][0].id)
    assert statement is not None
    assert statement.notification_status_code == NotificationStatus.SUCCESS.value


@pytest.mark.parametrize(
    "payment_method_code",
    [
        PaymentMethod.CASH.value,
        PaymentMethod.CC.value,
        PaymentMethod.DRAWDOWN.value,
        PaymentMethod.EJV.value,
        PaymentMethod.INTERNAL.value,
        PaymentMethod.ONLINE_BANKING.value,
        PaymentMethod.PAD.value,
    ],
)
def test_send_monthly_notifications_failed(setup, session, payment_method_code):  # pylint: disable=unused-argument
    """Test send monthly statement notifications failure."""
    # create statement, invoice, payment data for previous month
    last_month, last_year = get_previous_month_and_year()
    previous_month_year = datetime(last_year, last_month, 5)

    account, invoice, inv_ref, payment, statement_recipient, statement_settings = create_test_data(
        payment_method_code, previous_month_year, StatementFrequency.MONTHLY.value
    )

    assert invoice.payment_method_code == payment_method_code
    assert account.payment_method == payment_method_code

    # Generate statement for previous month - freeze time to the 1st of the current month
    with freeze_time(datetime.now(tz=timezone.utc).replace(day=1, hour=8)):
        StatementTask.generate_statements()

    # Assert statements and invoice was created
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements) == 2  # items results and page total
    assert len(statements[0]) == 1  # items
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Assert notification send_email was invoked
    with patch.object(StatementNotificationTask, "send_email", return_value=False) as mock_mailer:
        with patch("tasks.statement_notification_task.get_token") as mock_get_token:
            mock_get_token.return_value = "mock_token"
            StatementNotificationTask.send_notifications()
            mock_get_token.assert_called_once()
            # Assert token and email recipient - mock any for HTML generated
            mock_mailer.assert_called_with(mock_get_token.return_value, statement_recipient.email, ANY)

    # Assert statement notification code indicates failed
    statement: Statement = Statement.find_by_id(statements[0][0].id)
    assert statement is not None
    assert statement.notification_status_code == NotificationStatus.FAILED.value


def test_send_eft_notifications(setup, session):  # pylint: disable=unused-argument
    """Test send monthly EFT statement notifications."""
    # create statement, invoice, payment data for previous month
    last_month, last_year = get_previous_month_and_year()
    previous_month_year = datetime(last_year, last_month, 5)
    account, invoice, inv_ref, payment, statement_recipient, statement_settings = create_test_data(
        PaymentMethod.EFT.value,
        previous_month_year,
        StatementFrequency.MONTHLY.value,
        351.50,
    )

    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert account.payment_method == PaymentMethod.EFT.value

    # Generate statement for previous month - freeze time to the 1st of the current month
    with freeze_time(datetime.now(tz=timezone.utc).replace(day=1, hour=8)):
        StatementTask.generate_statements()

    # Assert statements and invoice was created
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements) == 2  # items results and page total
    assert len(statements[0]) == 1  # items
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Assert notification was published to the mailer queue
    with patch("tasks.statement_notification_task.publish_statement_notification") as mock_mailer:
        with patch("tasks.statement_notification_task.get_token") as mock_get_token:
            mock_get_token.return_value = "mock_token"
            StatementNotificationTask.send_notifications()
            mock_get_token.assert_called_once()
            mock_mailer.assert_called_once_with(account, statements[0][0], 351.5, statement_recipient.email)

    # Assert statement notification code indicates success
    statement: Statement = Statement.find_by_id(statements[0][0].id)
    assert statement is not None
    assert statement.notification_status_code == NotificationStatus.SUCCESS.value


def test_send_eft_notifications_failure(setup, session):  # pylint: disable=unused-argument
    """Test send monthly EFT statement notifications failure."""
    # create statement, invoice, payment data for previous month
    last_month, last_year = get_previous_month_and_year()
    previous_month_year = datetime(last_year, last_month, 5)
    account, invoice, inv_ref, payment, statement_recipient, statement_settings = create_test_data(
        PaymentMethod.EFT.value,
        previous_month_year,
        StatementFrequency.MONTHLY.value,
        351.50,
    )

    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert account.payment_method == PaymentMethod.EFT.value

    # Generate statement for previous month - freeze time to the 1st of the current month
    with freeze_time(datetime.now(tz=timezone.utc).replace(day=1, hour=8)):
        StatementTask.generate_statements()

    # Assert statements and invoice was created
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements) == 2  # items results and page total
    assert len(statements[0]) == 1  # items
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Assert notification was published to the mailer queue
    with patch("tasks.statement_notification_task.publish_statement_notification") as mock_mailer:
        mock_mailer.side_effect = Exception("Mock Exception")
        with patch("tasks.statement_notification_task.get_token") as mock_get_token:
            mock_get_token.return_value = "mock_token"
            StatementNotificationTask.send_notifications()
            mock_get_token.assert_called_once()
            mock_mailer.assert_called_once_with(account, statements[0][0], 351.5, statement_recipient.email)

    # Assert statement notification code indicates failed
    statement: Statement = Statement.find_by_id(statements[0][0].id)
    assert statement is not None
    assert statement.notification_status_code == NotificationStatus.FAILED.value
