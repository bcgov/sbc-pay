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

"""Tests to assure the Statement Service.

Test-Suite to ensure that the Statement Service is working as expected.
"""
from datetime import datetime, timedelta

from freezegun import freeze_time

from pay_api.models import PaymentAccount
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.services.statement_settings import StatementSettings as StatementSettingsService
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import StatementFrequency
from pay_api.utils.util import get_first_and_last_dates_of_month, get_week_start_and_end_date
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_premium_payment_account,
    factory_statement_settings)


def test_statement_settings_basic(session):
    """Assert basic service works."""
    statement_settings = StatementSettingsService()
    statement_settings.id = 1
    statement_settings.from_date = datetime.fromisoformat('2022-01-01')
    statement_settings.to_date = datetime.fromisoformat('2022-01-01')
    statement_settings.payment_account_id = 1
    data = statement_settings.asdict()
    assert data
    assert data['id'] == 1
    assert data['from_date'] == '2022-01-01'
    assert data['to_date'] == '2022-01-01'
    assert 'payment_account_id' not in data


def test_statement_settings_find_by_account(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_statement_settings(payment_account_id=bcol_account.id,
                               frequency=StatementFrequency.DAILY.value)

    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statement_settings = StatementSettingsService.find_by_account_id(payment_account.auth_account_id)
    assert statement_settings is not None
    assert statement_settings.get('current_frequency').get('frequency') == StatementFrequency.DAILY.value


def test_statement_settings_find_by_invalid_account(session):
    """Assert that the statement settings by id works."""
    statement_settings = StatementSettingsService.find_by_account_id('someaccountid')
    assert bool(statement_settings) is False


def test_update_statement_daily(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_statement_settings(payment_account_id=bcol_account.id,
                               frequency=StatementFrequency.DAILY.value)

    # update to weekly
    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.WEEKLY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.WEEKLY.value
    assert statement_settings.get('to_date') is None

    # daily to weekly - assert weekly should start by next week first day
    end_of_week_date = get_week_start_and_end_date()[1]
    assert statement_settings.get('from_date') == (end_of_week_date + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # daily to weekly - assert current active one is stil daily ending end of the week
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.DAILY.value
    assert current_statement_settings.to_date == end_of_week_date.date()

    # travel to next week and see whats active
    with freeze_time(end_of_week_date + timedelta(days=2)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.WEEKLY.value
        assert next_week_statement_settings.to_date is None

    # update to Monthly - assert monthly start by next month
    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.MONTHLY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.MONTHLY.value
    assert statement_settings.get('to_date') is None

    # daily to monthly - assert monthly should start by next month first day
    end_of_month_date = get_first_and_last_dates_of_month(datetime.today().month, datetime.today().year)[1]
    assert statement_settings.get('from_date') == (end_of_month_date + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # current one is still Ddaily , but ending end of the month
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.DAILY.value
    assert current_statement_settings.to_date == end_of_month_date.date()

    # travel to next month and see whats active
    with freeze_time(end_of_month_date + timedelta(days=2)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.MONTHLY.value
        assert next_week_statement_settings.to_date is None

    # update back to DAILY

    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.DAILY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.DAILY.value
    assert statement_settings.get('to_date') is None

    # daily to monthly - assert daily should Tomorrow
    assert statement_settings.get('from_date') == (datetime.today() + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # current one is still daily , but ending Today
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.DAILY.value
    assert current_statement_settings.to_date == datetime.today().date()

    # travel to next month and see whats active
    with freeze_time(end_of_month_date + timedelta(days=2)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.DAILY.value
        assert next_week_statement_settings.to_date is None


def test_update_statement_daily_to_daily(session):
    """Assert that going from daily to daily creates a new record."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_statement_settings(payment_account_id=bcol_account.id,
                               frequency=StatementFrequency.DAILY.value)

    # update to weekly
    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.DAILY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.DAILY.value
    assert statement_settings.get('to_date') is None

    # daily to daily - assert daily should start by tomorow
    assert statement_settings.get('from_date') == (datetime.today() + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # daily to daily - assert current active one is stil daily ending today
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.DAILY.value
    assert current_statement_settings.to_date == datetime.today().date()


def test_update_statement_monthly(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_statement_settings(payment_account_id=bcol_account.id,
                               frequency=StatementFrequency.MONTHLY.value)

    # update to weekly
    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.WEEKLY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.WEEKLY.value
    assert statement_settings.get('to_date') is None

    # monthly to weekly - assert weekly should start by next week first day
    end_of_month_date = get_first_and_last_dates_of_month(datetime.today().month, datetime.today().year)[1]
    assert statement_settings.get('from_date') == (end_of_month_date + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # monthly to weekly - assert current active one is stil monthly ending end of the week
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert current_statement_settings.to_date == end_of_month_date.date()

    # travel to next week and see whats active
    with freeze_time(end_of_month_date + timedelta(days=2)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.WEEKLY.value
        assert next_week_statement_settings.to_date is None


def test_update_statement_weekly(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_statement_settings(payment_account_id=bcol_account.id,
                               frequency=StatementFrequency.WEEKLY.value)

    # update to weekly
    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.WEEKLY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.WEEKLY.value
    assert statement_settings.get('to_date') is None

    # weekly to weekly - assert weekly should start by next week first day
    end_of_week_date = get_week_start_and_end_date()[1]
    assert statement_settings.get('from_date') == (end_of_week_date + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # daily to weekly - assert current active one is stil daily ending end of the week
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert current_statement_settings.to_date == end_of_week_date.date()

    # travel to next week and see whats active
    with freeze_time(end_of_week_date + timedelta(days=2)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.WEEKLY.value
        assert next_week_statement_settings.to_date is None

    # update to Monthly - assert monthly start by next month
    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.MONTHLY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.MONTHLY.value
    assert statement_settings.get('to_date') is None

    # weekly to monthly - assert monthly should start by next month first day
    end_of_month_date = get_first_and_last_dates_of_month(datetime.today().month, datetime.today().year)[1]
    assert statement_settings.get('from_date') == (end_of_month_date + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # current one is still weekly , but ending end of the month
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert current_statement_settings.to_date == end_of_month_date.date()

    # travel to next month and see whats active
    with freeze_time(end_of_month_date + timedelta(days=2)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.MONTHLY.value
        assert next_week_statement_settings.to_date is None

    # WEEKLY  to DAILY

    statement_settings = StatementSettingsService.update_statement_settings(payment_account.auth_account_id,
                                                                            StatementFrequency.DAILY.value)
    assert statement_settings is not None
    assert statement_settings.get('frequency') == StatementFrequency.DAILY.value
    assert statement_settings.get('to_date') is None

    # weekly to daily - assert daily should start next week first day
    assert statement_settings.get('from_date') == (end_of_week_date + timedelta(days=1)).strftime(DT_SHORT_FORMAT)

    # current one is still weekly , but ending end of the week
    current_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                             datetime.today())
    assert current_statement_settings is not None
    assert current_statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert current_statement_settings.to_date == end_of_week_date.date()

    # travel to next month and see whats active
    with freeze_time(end_of_month_date + timedelta(days=7)):
        next_week_statement_settings = StatementSettingsModel.find_active_settings(payment_account.auth_account_id,
                                                                                   datetime.today())
        assert next_week_statement_settings is not None
        assert next_week_statement_settings.frequency == StatementFrequency.DAILY.value
        assert next_week_statement_settings.to_date is None
