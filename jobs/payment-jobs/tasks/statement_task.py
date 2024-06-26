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

from datetime import datetime, timedelta

from dateutil.parser import parse
from flask import current_app
from pay_api.models.base_model import db
from pay_api.models.payment import Payment as PaymentModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_invoices import StatementInvoices as StatementInvoicesModel
from pay_api.models.statement_settings import StatementSettings as StatementSettingsModel
from pay_api.utils.enums import NotificationStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import (
    get_first_and_last_dates_of_month, get_local_time, get_previous_day, get_previous_month_and_year,
    get_week_start_and_end_date)
from sqlalchemy import delete


class StatementTask:  # pylint:disable=too-few-public-methods
    """Task to generate statements."""

    has_date_override: bool = False
    has_account_override: bool = False

    @classmethod
    def generate_statements(cls, arguments=None):
        """Generate statements.

        Steps:
        1. Get all payment accounts and it's active statement settings.
        """
        date_override = arguments[0] if arguments and len(arguments) > 0 else None
        auth_account_override = arguments[1] if arguments and len(arguments) > 1 else None

        target_time = get_local_time(datetime.now()) if date_override is None \
            else datetime.strptime(date_override, '%Y-%m-%d') + timedelta(days=1)
        cls.has_date_override = date_override is not None
        cls.has_account_override = auth_account_override is not None
        if date_override:
            current_app.logger.debug(f'Generating statements for: {date_override} using date override.')
        if auth_account_override:
            current_app.logger.debug(f'Generating statements for: {auth_account_override} using account override.')
        # If today is sunday - generate all weekly statements for pervious week
        # If today is month beginning - generate all monthly statements for previous month
        # For every day generate all daily statements for previous day
        generate_weekly = target_time.weekday() == 6  # Sunday is 6
        generate_monthly = target_time.day == 1

        cls._generate_daily_statements(target_time, auth_account_override)
        if generate_weekly:
            cls._generate_weekly_statements(target_time, auth_account_override)
        if generate_monthly:
            cls._generate_monthly_statements(target_time, auth_account_override)

        # Commit transaction
        db.session.commit()

    @classmethod
    def _generate_daily_statements(cls, target_time: datetime, account_override: str):
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
        cls._create_statement_records(search_filter, statement_settings, account_override)

    @classmethod
    def _generate_weekly_statements(cls, target_time: datetime, account_override: str):
        """Generate weekly statements for all accounts with settings to generate weekly."""
        previous_day = get_previous_day(target_time)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_day,
                                                                                        StatementFrequency.WEEKLY)
        current_app.logger.debug(f'Found {len(statement_settings)} accounts to generate WEEKLY statements')
        statement_from, statement_to = get_week_start_and_end_date(previous_day, index=1)
        search_filter = {
            'dateFilter': {
                'startDate': statement_from.strftime('%Y-%m-%d'),
                'endDate': statement_to.strftime('%Y-%m-%d')
            }
        }

        cls._create_statement_records(search_filter, statement_settings, account_override)

    @classmethod
    def _generate_monthly_statements(cls, target_time: datetime, account_override: str):
        """Generate monthly statements for all accounts with settings to generate monthly."""
        previous_day = get_previous_day(target_time)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_day,
                                                                                        StatementFrequency.MONTHLY)
        current_app.logger.debug(f'Found {len(statement_settings)} accounts to generate MONTHLY statements')
        last_month, last_month_year = get_previous_month_and_year(target_time)
        search_filter = {
            'monthFilter': {
                'month': last_month,
                'year': last_month_year
            }
        }

        cls._create_statement_records(search_filter, statement_settings, account_override)

    @classmethod
    def _create_statement_records(cls, search_filter, statement_settings, account_override: str):
        statement_from = None
        statement_to = None
        if search_filter.get('dateFilter', None):
            statement_from = parse(search_filter.get('dateFilter').get('startDate'))
            statement_to = parse(search_filter.get('dateFilter').get('endDate'))
            if statement_from == statement_to:
                current_app.logger.debug(f'Statements for day: {statement_from.date()}')
            else:
                current_app.logger.debug(f'Statements for week: {statement_from.date()} to {statement_to.date()}')
        elif search_filter.get('monthFilter', None):
            statement_from, statement_to = get_first_and_last_dates_of_month(
                search_filter.get('monthFilter').get('month'), search_filter.get('monthFilter').get('year'))
            current_app.logger.debug(f'Statements for month: {statement_from.date()} to {statement_to.date()}')
        if cls.has_account_override:
            auth_account_ids = [account_override]
            statement_settings = cls._filter_settings_by_override(statement_settings, account_override)
            current_app.logger.debug(f'Override Filtered to {len(statement_settings)} accounts to generate statements.')
        else:
            auth_account_ids = [pay_account.auth_account_id for _, pay_account in statement_settings]
        search_filter['authAccountIds'] = auth_account_ids
        # Force match on these methods where if the payment method is in matchPaymentMethods, the invoice payment method
        # must match the account payment method. Used for EFT so the statements only show EFT invoices and interim
        # statement logic when transitioning payment methods
        search_filter['matchPaymentMethods'] = [PaymentMethod.EFT.value]
        invoices_and_auth_ids = PaymentModel.get_invoices_for_statements(search_filter)
        if cls.has_date_override and statement_settings:
            cls._clean_up_old_statements(statement_settings, statement_from, statement_to)
        current_app.logger.debug('Inserting statements.')
        statements = [StatementModel(
            frequency=setting.frequency,
            statement_settings_id=setting.id,
            payment_account_id=pay_account.id,
            created_on=get_local_time(datetime.now()),
            from_date=statement_from,
            to_date=statement_to,
            notification_status_code=NotificationStatus.PENDING.value
            if pay_account.statement_notification_enabled is True and cls.has_date_override is False
            else NotificationStatus.SKIP.value
        ) for setting, pay_account in statement_settings]
        # Return defaults which returns the id.
        db.session.bulk_save_objects(statements, return_defaults=True)
        db.session.flush()

        current_app.logger.debug('Inserting statement invoices.')
        statement_invoices = []
        for statement, auth_account_id in zip(statements, auth_account_ids):
            invoices = [i for i in invoices_and_auth_ids if i.auth_account_id == auth_account_id]
            statement_invoices = statement_invoices + [StatementInvoicesModel(
                statement_id=statement.id,
                invoice_id=invoice.id
            ) for invoice in invoices]
        db.session.bulk_save_objects(statement_invoices)

    @classmethod
    def _clean_up_old_statements(cls, statement_settings, statement_from, statement_to):
        """Clean up duplicate / old statements before generating."""
        payment_account_ids = [pay_account.id for _, pay_account in statement_settings]
        remove_statements = db.session.query(StatementModel)\
            .filter_by(
                frequency=statement_settings[0].StatementSettings.frequency,
                from_date=statement_from.date(), to_date=statement_to.date())\
            .filter(StatementModel.payment_account_id.in_(payment_account_ids))\
            .all()
        current_app.logger.debug(f'Removing {len(remove_statements)} existing duplicate/stale statements.')
        remove_statements_ids = [statement.id for statement in remove_statements]
        remove_statement_invoices = db.session.query(StatementInvoicesModel)\
            .filter(StatementInvoicesModel.statement_id.in_(remove_statements_ids))\
            .all()
        statement_invoice_ids = [statement_invoice.id for statement_invoice in remove_statement_invoices]
        delete_statement_invoice = delete(StatementInvoicesModel)\
            .where(StatementInvoicesModel.id.in_(statement_invoice_ids))
        db.session.execute(delete_statement_invoice)
        db.session.flush()
        delete_statement = delete(StatementModel).where(StatementModel.id.in_(remove_statements_ids))
        db.session.execute(delete_statement)

    @classmethod
    def _filter_settings_by_override(cls, statement_settings, auth_account_id: str):
        """Return filtered Statement settings by payment account."""
        if statement_settings:
            return [settings
                    for settings in statement_settings
                    if settings.PaymentAccount.auth_account_id == auth_account_id]
