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
from datetime import datetime, timedelta, timezone

import pytz
import pytest
from freezegun import freeze_time
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Statement, StatementInvoices, StatementSettings, db
from pay_api.services import Statement as StatementService
from pay_api.services import StatementSettings as StatementSettingsService
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import get_previous_day
from sqlalchemy import insert

from tasks.statement_task import StatementTask

from .factory import (
    factory_create_account, factory_eft_account_payload, factory_invoice, factory_invoice_reference,
    factory_pad_account_payload, factory_payment, factory_premium_payment_account, factory_statement_settings)


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

    statements = StatementService.get_account_statements(auth_account_id=bcol_account.auth_account_id,
                                                         page=1, limit=100)
    assert statements is not None
    first_statement_id = statements[0][0].id
    invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Test date override.
    # Override computes for the target date, not the previous date like above.
    StatementTask.generate_statements([(datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')])

    statements = StatementService.get_account_statements(auth_account_id=bcol_account.auth_account_id,
                                                         page=1, limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Check to see if the old statement was reused and invoices were cleaned up.
    assert Statement.find_by_id(first_statement_id)
    assert first_statement_id == statements[0][0].id
    assert len(StatementInvoices.find_all_invoices_for_statement(first_statement_id)) == 2


def test_statements_for_empty_results(session):
    """Test daily statement generation works.

    Steps:
    1) Create a payment for day before yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement does not contains payment records
    """
    day_before_yday = get_previous_day(datetime.now(tz=timezone.utc)) - timedelta(days=1)
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

    statements = StatementService.get_account_statements(auth_account_id=bcol_account.auth_account_id,
                                                         page=1, limit=100)
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
                                     status_code=InvoiceStatus.APPROVED.value,
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
                                      status_code=InvoiceStatus.APPROVED.value,
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
                                   status_code=InvoiceStatus.APPROVED.value,
                                   total=50)

    assert bcol_invoice is not None
    direct_pay_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                         payment_method_code=PaymentMethod.DIRECT_PAY.value,
                                         status_code=InvoiceStatus.APPROVED.value,
                                         total=50)
    assert direct_pay_invoice

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
    account.payment_method_code = PaymentMethod.EFT.value
    account.save()

    # Validate bcol monthly interim invoice is correct
    invoices = StatementInvoices.find_all_invoices_for_statement(bcol_monthly_statement.id)
    assert invoices is not None
    assert len(invoices) == 2
    assert invoices[0].invoice_id == bcol_invoice.id
    assert invoices[1].invoice_id == direct_pay_invoice.id

    # Generate monthly statement using the 1st of next month
    generate_date = localize_date(datetime(2023, 11, 1, 12, 0))
    with freeze_time(generate_date):
        StatementTask.generate_statements()

    # Validate there are no invoices associated with this statement
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)
    assert statements is not None
    assert len(statements[0]) == 2
    first_statement_id = statements[0][0].id
    # Test invoices existing and payment_account.payment_method_code fallback.
    assert statements[0][0].payment_methods == PaymentMethod.EFT.value
    assert statements[0][1].payment_methods in [f'{PaymentMethod.DIRECT_PAY.value},{PaymentMethod.DRAWDOWN.value}',
                                                f'{PaymentMethod.DRAWDOWN.value},{PaymentMethod.DIRECT_PAY.value}']
    monthly_invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert len(monthly_invoices) == 0

    # Set up and EFT invoice
    # Using the same invoice create date as the weekly to test invoices on the same day with different payment methods
    monthly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                      payment_method_code=PaymentMethod.EFT.value,
                                      status_code=InvoiceStatus.APPROVED.value,
                                      total=50)

    assert monthly_invoice is not None
    # This should get ignored.
    monthly_invoice_2 = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                        payment_method_code=PaymentMethod.DIRECT_PAY.value,
                                        status_code=InvoiceStatus.APPROVED.value,
                                        total=50)
    assert monthly_invoice_2

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
    # This should be EFT only, because there's a filter in the jobs that looks only for EFT invoices if
    # payment_account is set to EFT.
    assert statements[0][0].payment_methods == f'{PaymentMethod.EFT.value}'

    # Validate bcol monthly interim invoice is correct
    bcol_invoices = StatementInvoices.find_all_invoices_for_statement(bcol_monthly_statement.id)
    assert bcol_invoices is not None
    assert len(bcol_invoices) == 2
    assert bcol_invoices[0].invoice_id == bcol_invoice.id
    assert bcol_invoices[1].invoice_id == direct_pay_invoice.id


def test_many_statements():
    """Ensure many statements work over 65535 statements."""
    account = factory_create_account(auth_account_id='1')
    factory_statement_settings(
        pay_account_id=account.id,
        from_date=datetime(2024, 1, 1, 8),
        to_date=datetime(2024, 1, 4, 8),
        frequency=StatementFrequency.DAILY.value
    ).save()
    invoice = factory_invoice(account)
    statement_list = []
    for _ in range(0, 70000):
        statement_list.append({'created_on': '2024-01-01',
                               'from_date': '2024-01-01 08:00:00',
                               'to_date': '2024-01-04 08:00:00',
                               'payment_account_id': f'{account.id}',
                               'frequency': StatementFrequency.DAILY.value
                               })
    db.session.execute(insert(Statement), statement_list)

    statement = db.session.query(Statement).first()
    statement_invoices_list = []
    for _ in range(0, 70000):
        statement_invoices_list.append({
            'statement_id': statement.id,
            'invoice_id': invoice.id
        })
    db.session.execute(insert(StatementInvoices), statement_invoices_list)
    StatementTask.generate_statements([datetime(2024, 1, 1, 8).strftime('%Y-%m-%d')])
    assert True


@pytest.mark.parametrize('test_name', [('non_interm'), ('pad_to_eft'), ('eft_to_pad')])
def test_gap_statements(session, test_name, admin_users_mock):
    """Ensure gap statements are generated for weekly to monthly."""
    account_create_date = datetime(2024, 1, 1, 8)
    account = None
    invoice_ids = []
    with freeze_time(account_create_date):
        match test_name:
            case 'eft_to_pad':
                account = factory_create_account(auth_account_id='1', payment_method_code=PaymentMethod.EFT.value)
            case _:
                account = factory_create_account(auth_account_id='1', payment_method_code=PaymentMethod.PAD.value)

    from_date = (localize_date(datetime(2024, 1, 1, 8))).date()
    StatementInvoices.query.delete()
    Statement.query.delete()
    StatementSettings.query.delete()
    InvoiceModel.query.delete()
    factory_statement_settings(pay_account_id=account.id,
                               frequency=StatementFrequency.WEEKLY.value,
                               from_date=from_date
                               ).save()

    # Generate invoices for January 1st -> January 31st.
    match test_name:
        case 'non_interm':
            for i in range(0, 31):
                inv = factory_invoice(payment_account=account,
                                      payment_method_code=PaymentMethod.PAD.value,
                                      status_code=InvoiceStatus.PAID.value,
                                      total=50,
                                      created_on=account_create_date + timedelta(i)) \
                    .save()
                invoice_ids.append(inv.id)
        case 'pad_to_eft':
            for i in range(0, 28):
                inv = factory_invoice(payment_account=account,
                                      payment_method_code=PaymentMethod.PAD.value,
                                      status_code=InvoiceStatus.PAID.value,
                                      total=50,
                                      created_on=account_create_date + timedelta(i)) \
                    .save()
                invoice_ids.append(inv.id)
            # Overlap an EFT invoice and PAD on the same day.
            for i in range(28, 31):
                inv = factory_invoice(payment_account=account,
                                      payment_method_code=PaymentMethod.EFT.value,
                                      status_code=InvoiceStatus.PAID.value,
                                      total=50,
                                      created_on=account_create_date + timedelta(i)) \
                    .save()
                invoice_ids.append(inv.id)
        case 'eft_to_pad':
            for i in range(0, 28):
                inv = factory_invoice(payment_account=account,
                                      payment_method_code=PaymentMethod.EFT.value,
                                      status_code=InvoiceStatus.PAID.value,
                                      total=50,
                                      created_on=account_create_date + timedelta(i)) \
                    .save()
                invoice_ids.append(inv.id)
            # Overlap an EFT invoice and PAD on the same day.
            for i in range(28, 31):
                inv = factory_invoice(payment_account=account,
                                      payment_method_code=PaymentMethod.PAD.value,
                                      status_code=InvoiceStatus.PAID.value,
                                      total=50,
                                      created_on=account_create_date + timedelta(i)) \
                    .save()
                invoice_ids.append(inv.id)

    match test_name:
        case 'non_interm':
            with freeze_time(datetime(2024, 1, 1, 8)):
                # This should create a gap between 28th Sunday and 31st Wednesday, this is a gap statement.
                StatementSettingsService.update_statement_settings(account.auth_account_id,
                                                                   StatementFrequency.MONTHLY.value)
            generate_statements(0, 32)
        case 'pad_to_eft':
            # Note: This will work even if we start off as MONTHLY or change to MONTHLY from weekly.
            # Generate up to the 28th before the interm statment.
            generate_statements(0, 28)
            with freeze_time(localize_date(datetime(2024, 1, 28, 8))):
                payload = factory_eft_account_payload(payment_method=PaymentMethod.EFT.value,
                                                      account_id=account.auth_account_id)
                PaymentAccountService.update(account.auth_account_id, payload)
            generate_statements(29, 32)
        case 'eft_to_pad':
            # Generate up to the 28th before the interm statment.
            generate_statements(0, 28)
            with freeze_time(localize_date(datetime(2024, 1, 28, 8))):
                # Update to PAD - Keep the pad activation_date in the past, otherwise we wont switch over to PAD.
                # If we can't switch to PAD, no invoices would be created until activation date was hit.
                account.pad_activation_date = datetime.now(tz=timezone.utc) - timedelta(days=1)
                account.save()
                PaymentAccountService.update(account.auth_account_id, factory_pad_account_payload())
            generate_statements(29, 32)

    statements = Statement.query.all()
    for statement in statements:
        assert statement.payment_methods != 'PAD,EFT'
        assert statement.payment_methods != 'EFT,PAD'

    generated_invoice_ids = [inv.invoice_id for inv in StatementInvoices.query.all()]

    assert len(invoice_ids) == len(generated_invoice_ids)


def generate_statements(start, end):
    """Generate statements helper."""
    for r in range(start, end):
        override_date = localize_date(datetime(2024, 1, 1, 8) + timedelta(days=r - 1)).strftime('%Y-%m-%d')
        StatementTask.generate_statements([override_date])


def localize_date(date: datetime):
    """Localize date object by adding timezone information."""
    pst = pytz.timezone('America/Vancouver')
    return pst.localize(date)
