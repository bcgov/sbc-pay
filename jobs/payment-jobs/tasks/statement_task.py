# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage PAYBC services."""

from datetime import datetime

from dateutil.parser import parse
from flask import current_app
from pay_api.models.base_model import db
from pay_api.models.payment import Payment as PaymentModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_invoices import StatementInvoices as StatementInvoicesModel
from pay_api.models.statement_settings import StatementSettings as StatementSettingsModel
from pay_api.utils.enums import NotificationStatus, StatementFrequency
from pay_api.utils.util import (
    get_first_and_last_dates_of_month, get_local_time, get_previous_day, get_previous_month_and_year,
    get_week_start_and_end_date)


class StatementTask:  # pylint:disable=too-few-public-methods
    """Task to generate statements."""

    skip_notify: bool = False

    @classmethod
    def generate_statements(cls, date_override=None):
        """Generate statements.

        Steps:
        1. Get all payment accounts and it's active statement settings.
        """
        target_time = get_local_time(datetime.now()) if date_override is None \
            else datetime.strptime(date_override, '%Y-%m-%d')
        cls.skip_notify = date_override is not None
        if date_override:
            current_app.logger.debug(f'Generating statements for: {date_override} using date override,'
                                     ' this generates for the previous day/week/month.')
        # If today is sunday - generate all weekly statements for pervious week
        # If today is month beginning - generate all monthly statements for previous month
        # For every day generate all daily statements for previous day
        generate_weekly = target_time.weekday() == 6  # Sunday is 6
        generate_monthly = target_time.day == 1

        cls._generate_daily_statements(target_time)
        if generate_weekly:
            cls._generate_weekly_statements(target_time)
        if generate_monthly:
            cls._generate_monthly_statements(target_time)

        # Commit transaction
        db.session.commit()

    @classmethod
    def _generate_daily_statements(cls, target_time: datetime):
        """Generate daily statements for all accounts with settings to generate daily."""
        previous_day = get_previous_day(target_time)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_day,
                                                                                        StatementFrequency.DAILY)
        current_app.logger.debug(f'Found {len(statement_settings)} accounts to generate DAILY statements')
        search_filter = {
            'dateFilter': {
                'startDate': previous_day.strftime('%Y-%m-%d'),
                'endDate': previous_day.strftime('%Y-%m-%d')
            }
        }
        cls._create_statement_records(previous_day, search_filter, statement_settings)

    @classmethod
    def _generate_weekly_statements(cls, target_time: datetime):
        """Generate weekly statements for all accounts with settings to generate weekly."""
        previous_day = get_previous_day(target_time)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_day,
                                                                                        StatementFrequency.WEEKLY)
        current_app.logger.debug(f'Found {len(statement_settings)} accounts to generate WEEKLY statements')
        search_filter = {
            'weekFilter': {
                'index': 1  # previous week
            }
        }

        cls._create_statement_records(previous_day, search_filter, statement_settings)

    @classmethod
    def _generate_monthly_statements(cls, target_time: datetime):
        """Generate monthly statements for all accounts with settings to generate monthly."""
        previous_day = get_previous_day(target_time)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_day,
                                                                                        StatementFrequency.MONTHLY)
        current_app.logger.debug(f'Found {len(statement_settings)} accounts to generate MONTHLY statements')
        last_month, last_month_year = get_previous_month_and_year()
        search_filter = {
            'monthFilter': {
                'month': last_month,
                'year': last_month_year
            }
        }

        cls._create_statement_records(previous_day, search_filter, statement_settings)

    @classmethod
    def _create_statement_records(cls, previous_day, search_filter, statement_settings):
        statement_from = None
        statement_to = None
        if search_filter.get('dateFilter', None):
            statement_from = parse(search_filter.get('dateFilter').get('startDate'))
            statement_to = parse(search_filter.get('dateFilter').get('endDate'))
            current_app.logger.debug(f'Statements for day: {statement_from.date()}')
        elif search_filter.get('weekFilter', None):
            index = search_filter.get('weekFilter').get('index')
            statement_from, statement_to = get_week_start_and_end_date(target_date=previous_day, index=index)
            current_app.logger.debug(f'Statements for week: {statement_from.date()} to {statement_to.date()}')
        elif search_filter.get('monthFilter', None):
            statement_from, statement_to = get_first_and_last_dates_of_month(
                search_filter.get('monthFilter').get('month'), search_filter.get('monthFilter').get('year'))
            current_app.logger.debug(f'Statements for month: {statement_from.date()} to {statement_to.date()}')
        auth_account_ids = [pay_account.auth_account_id for _, pay_account in statement_settings]
        search_filter['authAccountIds'] = auth_account_ids
        invoices_and_auth_ids = PaymentModel.get_invoices_for_statements(search_filter)
        statements = [StatementModel(
                frequency=setting.frequency,
                statement_settings_id=setting.id,
                payment_account_id=pay_account.id,
                created_on=get_local_time(datetime.now()),
                from_date=statement_from,
                to_date=statement_to,
                notification_status_code=NotificationStatus.PENDING.value
                if pay_account.statement_notification_enabled is True and cls.skip_notify is False
                else NotificationStatus.SKIP.value
        ) for setting, pay_account in statement_settings]
        # Return defaults which returns the id.
        db.session.bulk_save_objects(statements, return_defaults=True)
        db.session.flush()

        for statement, auth_account_id in zip(statements, auth_account_ids):
            invoices = [i for i in invoices_and_auth_ids if i.auth_account_id == auth_account_id]
            for invoice in invoices:
                statement_invoice = StatementInvoicesModel(
                    statement_id=statement.id,
                    invoice_id=invoice.id
                )
                db.session.add(statement_invoice)
