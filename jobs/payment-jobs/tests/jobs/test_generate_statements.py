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

"""Tests to assure the UpdateStalePayment.

Test-Suite to ensure that the UpdateStalePayment is working as expected.
"""
from datetime import datetime, timedelta

import pytz
from freezegun import freeze_time
from pay_api.models import Statement, StatementInvoices
from pay_api.services import Statement as StatementService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import get_previous_day

from tasks.statement_task import StatementTask

from .factory import (
    factory_create_account, factory_invoice, factory_invoice_reference, factory_payment,
    factory_premium_payment_account, factory_statement_settings)


@freeze_time('2023-01-02 12:00:00T08:00:00')
def test_statements(session):
    """Test daily statement generation works.

    Steps:
    1) Create a payment for yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement contains payment records
    """
    previous_day = localize_date(get_previous_day(datetime.utcnow()))

    bcol_account = factory_premium_payment_account()
    invoice = factory_invoice(payment_account=bcol_account, created_on=previous_day)
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(payment_date=previous_day, invoice_number=inv_ref.invoice_number)

    factory_statement_settings(
        pay_account_id=bcol_account.id,
        from_date=previous_day,
        frequency='DAILY'
    )
    factory_statement_settings(
        pay_account_id=bcol_account.id,
        from_date=get_previous_day(previous_day),
        frequency='DAILY'
    )
    factory_statement_settings(
        pay_account_id=bcol_account.id,
        from_date=datetime.utcnow(),
        frequency='DAILY'
    )
    StatementTask.generate_statements()

    statements = StatementService.get_account_statements(auth_account_id=bcol_account.auth_account_id, page=1, limit=100)
    assert statements is not None
    first_statement_id = statements[0][0].id
    invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Test date override.
    # Override computes for the target date, not the previous date like above.
    StatementTask.generate_statements([(datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')])

    statements = StatementService.get_account_statements(auth_account_id=bcol_account.auth_account_id, page=1, limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Check to see if the old statement / invoices were cleaned up.
    assert Statement.find_by_id(first_statement_id) is None
    assert StatementInvoices.find_all_invoices_for_statement(first_statement_id) == []


def test_statements_for_empty_results(session):
    """Test daily statement generation works.

    Steps:
    1) Create a payment for day before yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement does not contains payment records
    """
    day_before_yday = get_previous_day(datetime.now()) - timedelta(days=1)
    bcol_account = factory_premium_payment_account()
    invoice = factory_invoice(payment_account=bcol_account, created_on=day_before_yday)
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_statement_settings(
        pay_account_id=bcol_account.id,
        from_date=day_before_yday,
        frequency='DAILY'
    )
    factory_payment(payment_date=day_before_yday, invoice_number=inv_ref.invoice_number)

    StatementTask.generate_statements()

    statements = StatementService.get_account_statements(auth_account_id=bcol_account.auth_account_id, page=1, limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert len(invoices) == 0


def test_bcol_weekly_to_eft_statement(session):
    """Test transition to EFT statement with an existing weekly interim statement."""
    # Account set up
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account = factory_create_account(auth_account_id='1', payment_method_code=PaymentMethod.EFT.value)
        assert account is not None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    weekly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                     payment_method_code=PaymentMethod.DRAWDOWN.value,
                                     status_code=InvoiceStatus.CREATED.value,
                                     total=50)

    assert weekly_invoice is not None

    statement_from_date = localize_date(datetime(2023, 10, 8, 12, 0))
    statement_to_date = localize_date(datetime(2023, 10, 12, 12, 0))

    # Set up initial statement settings
    factory_statement_settings(
        pay_account_id=account.id,
        from_date=statement_from_date,
        to_date=statement_to_date,
        frequency=StatementFrequency.WEEKLY.value
    ).save()

    generate_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(generate_date):
        weekly_statement = StatementService.generate_interim_statement(auth_account_id=account.auth_account_id,
                                                                       new_frequency=StatementFrequency.MONTHLY.value)

    # Validate weekly interim invoice is correct
    weekly_invoices = StatementInvoices.find_all_invoices_for_statement(weekly_statement.id)
    assert weekly_invoices is not None
    assert len(weekly_invoices) == 1
    assert weekly_invoices[0].invoice_id == weekly_invoice.id

    # Generate monthly statement using the 1st of next month
    generate_date = localize_date(datetime(2023, 11, 1, 12, 0))
    with freeze_time(generate_date):
        StatementTask.generate_statements()

    # Validate there are no invoices associated with this statement
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements[0]) == 2
    first_statement_id = statements[0][0].id
    monthly_invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert len(monthly_invoices) == 0

    # Set up and EFT invoice
    # Using the same invoice create date as the weekly to test invoices on the same day with different payment methods
    monthly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                      payment_method_code=PaymentMethod.EFT.value,
                                      status_code=InvoiceStatus.CREATED.value,
                                      total=50)

    assert monthly_invoice is not None

    # Regenerate monthly statement using date override - it will clean up the previous empty monthly statement first
    StatementTask.generate_statements([(generate_date - timedelta(days=1)).strftime('%Y-%m-%d')])

    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)

    assert statements is not None
    assert len(statements[0]) == 2  # Should still be 2 statements as the previous empty one should be removed
    first_statement_id = statements[0][0].id
    monthly_invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert monthly_invoices is not None
    assert len(monthly_invoices) == 1
    assert monthly_invoices[0].invoice_id == monthly_invoice.id


def test_bcol_monthly_to_eft_statement(session):
    """Test transition to EFT statement with an existing monthly interim statement."""
    # Account set up
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account = factory_create_account(auth_account_id='1', payment_method_code=PaymentMethod.EFT.value)
        assert account is not None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    bcol_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                   payment_method_code=PaymentMethod.DRAWDOWN.value,
                                   status_code=InvoiceStatus.CREATED.value,
                                   total=50)

    assert bcol_invoice is not None

    statement_from_date = localize_date(datetime(2023, 10, 1, 12, 0))
    statement_to_date = localize_date(datetime(2023, 10, 30, 12, 0))

    # Set up initial statement settings
    factory_statement_settings(
        pay_account_id=account.id,
        from_date=statement_from_date,
        to_date=statement_to_date,
        frequency=StatementFrequency.MONTHLY.value
    ).save()

    generate_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(generate_date):
        bcol_monthly_statement = StatementService\
            .generate_interim_statement(auth_account_id=account.auth_account_id,
                                        new_frequency=StatementFrequency.MONTHLY.value)

    # Validate bcol monthly interim invoice is correct
    bcol_invoices = StatementInvoices.find_all_invoices_for_statement(bcol_monthly_statement.id)
    assert bcol_invoices is not None
    assert len(bcol_invoices) == 1
    assert bcol_invoices[0].invoice_id == bcol_invoice.id

    # Generate monthly statement using the 1st of next month
    generate_date = localize_date(datetime(2023, 11, 1, 12, 0))
    with freeze_time(generate_date):
        StatementTask.generate_statements()

    # Validate there are no invoices associated with this statement
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements[0]) == 2
    first_statement_id = statements[0][0].id
    monthly_invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert len(monthly_invoices) == 0

    # Set up and EFT invoice
    # Using the same invoice create date as the weekly to test invoices on the same day with different payment methods
    monthly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                      payment_method_code=PaymentMethod.EFT.value,
                                      status_code=InvoiceStatus.CREATED.value,
                                      total=50)

    assert monthly_invoice is not None

    # Regenerate monthly statement using date override - it will clean up the previous empty monthly statement first
    StatementTask.generate_statements([(generate_date - timedelta(days=1)).strftime('%Y-%m-%d')])

    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)

    assert statements is not None
    assert len(statements[0]) == 2  # Should still be 2 statements as the previous empty one should be removed
    first_statement_id = statements[0][0].id
    monthly_invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert monthly_invoices is not None
    assert len(monthly_invoices) == 1
    assert monthly_invoices[0].invoice_id == monthly_invoice.id

    # Validate bcol monthly interim invoice is correct
    bcol_invoices = StatementInvoices.find_all_invoices_for_statement(bcol_monthly_statement.id)
    assert bcol_invoices is not None
    assert len(bcol_invoices) == 1
    assert bcol_invoices[0].invoice_id == bcol_invoice.id


def localize_date(date: datetime):
    """Localize date object by adding timezone information."""
    pst = pytz.timezone('America/Vancouver')
    return pst.localize(date)
