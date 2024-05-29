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

"""Tests to assure the Statement Service.

Test-Suite to ensure that the Statement Service is working as expected.
"""
from datetime import datetime

import pytz
from freezegun import freeze_time
from sqlalchemy import text

from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoiceModel
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.services.statement import Statement as StatementService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_line_item,
    factory_premium_payment_account, factory_statement, factory_statement_invoices, factory_statement_settings,
    get_auth_premium_user, get_basic_account_payload, get_eft_enable_account_payload, get_premium_account_payload,
    get_unlinked_pad_account_payload)


def test_statement_find_by_account(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account, status_code=InvoiceStatus.OVERDUE.value)
    i.save()
    factory_invoice_reference(i.id).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None
    assert statements.get('total') == 1
    assert statements.get('items')[0].get('is_overdue') is True


def test_get_statement_report(session):
    """Assert that the get statement report works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(statement_id=statement_model.id,
                                                                         content_type='application/pdf',
                                                                         auth=get_auth_premium_user())
    assert report_response is not None


def test_get_statement_report_for_empty_invoices(session):
    """Assert that the get statement report works for statement with no invoices."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(statement_id=statement_model.id,
                                                                         content_type='application/pdf',
                                                                         auth=get_auth_premium_user())
    assert report_response is not None


def test_get_weekly_statement_report(session):
    """Assert that the get statement report works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.WEEKLY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.WEEKLY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(statement_id=statement_model.id,
                                                                         content_type='application/pdf',
                                                                         auth=get_auth_premium_user())
    assert report_response is not None


def test_get_weekly_interim_statement(session, admin_users_mock):
    """Assert that a weekly interim statement is generated."""
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value))

        assert account is not None
        assert account.payment_method == PaymentMethod.DRAWDOWN.value

    # Assert that the default weekly statement settings are created
    statement_settings: StatementSettingsModel = StatementSettingsModel \
        .find_active_settings(str(account.auth_account_id), datetime.today())

    assert statement_settings is not None
    assert statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert statement_settings.from_date == account_create_date.date()
    assert statement_settings.to_date is None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    weekly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                     payment_method_code=PaymentMethod.DRAWDOWN.value,
                                     status_code=InvoiceStatus.CREATED.value,
                                     total=50).save()

    assert weekly_invoice is not None
    update_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(account.auth_account_id,
                                               get_eft_enable_account_payload(payment_method=PaymentMethod.EFT.value,
                                                                              account_id=account.auth_account_id))

        new_statement_settings: StatementSettingsModel = StatementSettingsModel \
            .find_latest_settings(account.auth_account_id)

        assert new_statement_settings is not None
        assert new_statement_settings.id != statement_settings.id
        assert new_statement_settings.frequency == StatementFrequency.MONTHLY.value
        assert new_statement_settings.to_date is None

    # Validate interim statement has the correct invoice
    statements = StatementModel.find_all_statements_for_account(auth_account_id=account.auth_account_id, page=1,
                                                                limit=100)

    assert statements is not None
    assert len(statements[0]) == 1

    # Validate weekly interim invoice is correct
    weekly_invoices = StatementInvoiceModel.find_all_invoices_for_statement(statements[0][0].id)
    assert weekly_invoices is not None
    assert len(weekly_invoices) == 1
    assert weekly_invoices[0].invoice_id == weekly_invoice.id


def test_get_interim_statement_change_away_from_eft(session, admin_users_mock):
    """Assert that a payment method update interim statement is generated."""
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_eft_enable_account_payload(payment_method=PaymentMethod.EFT.value))

        assert account is not None
        assert account.payment_method == PaymentMethod.EFT.value

    # Assert that the default MONTHLY statement settings are created
    statement_settings: StatementSettingsModel = StatementSettingsModel \
        .find_active_settings(str(account.auth_account_id), datetime.today())

    assert statement_settings is not None
    assert statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert statement_settings.from_date == account_create_date.date()
    assert statement_settings.to_date is None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    monthly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                      payment_method_code=PaymentMethod.EFT.value,
                                      status_code=InvoiceStatus.CREATED.value,
                                      total=50).save()

    assert monthly_invoice is not None
    update_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(account.auth_account_id,
                                               get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value,
                                                                           account_id=account.auth_account_id))

        new_statement_settings: StatementSettingsModel = StatementSettingsModel \
            .find_latest_settings(account.auth_account_id)

        assert new_statement_settings is not None
        assert new_statement_settings.id != statement_settings.id
        assert new_statement_settings.to_date is None

    # Validate interim statement has the correct invoice
    statements = StatementModel.find_all_statements_for_account(auth_account_id=account.auth_account_id, page=1,
                                                                limit=100)

    assert statements is not None
    assert len(statements[0]) == 1

    # Validate interim invoice is correct
    interim_invoices = StatementInvoiceModel.find_all_invoices_for_statement(statements[0][0].id)
    assert interim_invoices is not None
    assert len(interim_invoices) == 1
    assert interim_invoices[0].invoice_id == monthly_invoice.id


def test_get_monthly_interim_statement(session, admin_users_mock):
    """Assert that a monthly interim statement is generated."""
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value))

        assert account is not None
        assert account.payment_method == PaymentMethod.DRAWDOWN.value

    # Update current active settings to monthly
    statement_settings: StatementSettingsModel = StatementSettingsModel \
        .find_active_settings(str(account.auth_account_id), datetime.today())

    statement_settings.frequency = StatementFrequency.MONTHLY.value
    statement_settings.save()

    assert statement_settings is not None
    assert statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert statement_settings.from_date == account_create_date.date()
    assert statement_settings.to_date is None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    monthly_invoice = factory_invoice(payment_account=account, created_on=invoice_create_date,
                                      payment_method_code=PaymentMethod.DRAWDOWN.value,
                                      status_code=InvoiceStatus.CREATED.value,
                                      total=50).save()

    assert monthly_invoice is not None

    update_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(account.auth_account_id,
                                               get_eft_enable_account_payload(payment_method=PaymentMethod.EFT.value,
                                                                              account_id=account.auth_account_id))

        new_statement_settings: StatementSettingsModel = StatementSettingsModel \
            .find_latest_settings(account.auth_account_id)

        assert new_statement_settings is not None
        assert new_statement_settings.id != statement_settings.id
        assert new_statement_settings.frequency == StatementFrequency.MONTHLY.value
        assert new_statement_settings.to_date is None

    # Validate interim statement has the correct invoice
    statements = StatementModel.find_all_statements_for_account(auth_account_id=account.auth_account_id, page=1,
                                                                limit=100)

    assert statements is not None
    assert len(statements[0]) == 1

    # Validate monthly interim invoice is correct
    monthly_invoices = StatementInvoiceModel.find_all_invoices_for_statement(statements[0][0].id)
    assert monthly_invoices is not None
    assert len(monthly_invoices) == 1
    assert monthly_invoices[0].invoice_id == monthly_invoice.id


def localize_date(date: datetime):
    """Localize date object by adding timezone information."""
    pst = pytz.timezone('America/Vancouver')
    return pst.localize(date)


def test_statement_various_payment_methods_history(db, app):
    """Unit test to test various payment methods over the life of a statement."""
    # We aren't using the session fixture here because we want to test the history_cls
    # history_cls wont work on scoped session flush.
    with app.app_context():
        db.session.commit = db.session.flush
        account: PaymentAccountService = PaymentAccountService.create(
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value))

        statement_settings: StatementSettingsModel = StatementSettingsModel \
            .find_active_settings(str(account.auth_account_id), datetime.today())

        statement = StatementModel(
            statement_settings_id=statement_settings.id,
            payment_account_id=account.id,
            created_on=datetime.today(),
            from_date=datetime(2024, 1, 2, 12, 0).date(),
            to_date=datetime(2024, 1, 7, 12, 0).date()
        ).flush()

        account = PaymentAccountService.update(account.auth_account_id, get_unlinked_pad_account_payload())
        # History row wont be generated for this line:
        account = PaymentAccountService.update(account.auth_account_id, get_basic_account_payload())
        # Freezegun, pytest-freezegun don't work here.
        db.session.execute(text("update payment_accounts_history set changed = '2024-01-02' "
                                f"where payment_method = '{PaymentMethod.DRAWDOWN.value}'"))
        db.session.execute(text("update payment_accounts_history set changed = '2024-01-03' "
                                f"where payment_method = '{PaymentMethod.PAD.value}'"))

        payment_methods = statement.payment_methods
        assert 'DIRECT_PAY' in payment_methods
        assert 'DRAWDOWN' in payment_methods
        assert 'PAD' in payment_methods
