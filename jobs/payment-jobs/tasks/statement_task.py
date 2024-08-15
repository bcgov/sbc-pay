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

from datetime import datetime, timedelta, timezone

from dateutil.parser import parse
from flask import current_app
from pay_api.models.base_model import db
from pay_api.models.payment import Payment as PaymentModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_invoices import StatementInvoices as StatementInvoicesModel
from pay_api.models.statement_settings import StatementSettings as StatementSettingsModel
from pay_api.services.statement import Statement as StatementService
from pay_api.utils.enums import NotificationStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import (
    get_first_and_last_dates_of_month, get_local_time, get_previous_day, get_previous_month_and_year,
    get_week_start_and_end_date)
from sqlalchemy import cast, delete, func, select
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER


class StatementTask:  # pylint:disable=too-few-public-methods
    """Task to generate statements."""

    has_date_override: bool = False
    has_account_override: bool = False
    statement_from: datetime = None
    statement_to: datetime = None

    @classmethod
    def generate_statements(cls, arguments=None):
        """Generate statements.

        Steps:
        1. Get all payment accounts and it's active statement settings.
        """
        date_override = arguments[0] if arguments and len(arguments) > 0 else None
        auth_account_override = arguments[1] if arguments and len(arguments) > 1 else None

        target_time = get_local_time(datetime.now(tz=timezone.utc)) if date_override is None \
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
    def _upsert_statements(cls, statement_settings, invoice_detail_tuple, reuse_statements):
        """Upsert statements to reuse statement ids because they are referenced in the EFT Shortname History."""
        statements = []
        for setting, pay_account in statement_settings:
            existing_statement = next(
                    (statement for statement in reuse_statements
                     if statement.payment_account_id == pay_account.id and
                     statement.frequency == setting.frequency and
                     statement.from_date == cls.statement_from.date() and statement.to_date == cls.statement_to.date()),
                    None
                   )
            notification_status = NotificationStatus.PENDING.value \
                if pay_account.statement_notification_enabled is True and cls.has_date_override is False \
                else NotificationStatus.SKIP.value
            payment_methods = StatementService.determine_payment_methods(invoice_detail_tuple,
                                                                         pay_account,
                                                                         existing_statement)
            created_on = get_local_time(datetime.now(tz=timezone.utc))
            if existing_statement:
                current_app.logger.debug(f'Reusing existing statement already exists for {cls.statement_from.date()}')
                existing_statement.notification_status_code = notification_status
                existing_statement.payment_methods = payment_methods
                existing_statement.created_on = created_on
                statements.append(existing_statement)
            else:
                statements.append(StatementModel(
                    frequency=setting.frequency,
                    statement_settings_id=setting.id,
                    payment_account_id=pay_account.id,
                    created_on=created_on,
                    from_date=cls.statement_from,
                    to_date=cls.statement_to,
                    notification_status_code=notification_status,
                    payment_methods=payment_methods
                ))
        return statements

    @classmethod
    def _create_statement_records(cls, search_filter, statement_settings, account_override: str):
        cls.statement_from = None
        cls.statement_to = None
        if search_filter.get('dateFilter', None):
            cls.statement_from = parse(search_filter.get('dateFilter').get('startDate'))
            cls.statement_to = parse(search_filter.get('dateFilter').get('endDate'))
            if cls.statement_from == cls.statement_to:
                current_app.logger.debug(f'Statements for day: {cls.statement_from.date()}')
            else:
                current_app.logger.debug(f'Statements for week: {cls.statement_from.date()} to '
                                         f'{cls.statement_to.date()}')
        elif search_filter.get('monthFilter', None):
            cls.statement_from, cls.statement_to = get_first_and_last_dates_of_month(
                search_filter.get('monthFilter').get('month'), search_filter.get('monthFilter').get('year'))
            current_app.logger.debug(f'Statements for month: {cls.statement_from.date()} to {cls.statement_to.date()}')
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
        invoice_detail_tuple = PaymentModel.get_invoices_and_payment_accounts_for_statements(search_filter)
        reuse_statements = []
        if cls.has_date_override and statement_settings:
            reuse_statements = cls._clean_up_old_statements(statement_settings)
        current_app.logger.debug('Upserting statements.')
        statements = cls._upsert_statements(statement_settings, invoice_detail_tuple, reuse_statements)
        # Return defaults which returns the id.
        db.session.bulk_save_objects(statements, return_defaults=True)
        db.session.flush()

        current_app.logger.debug('Inserting statement invoices.')
        statement_invoices = []
        for statement, auth_account_id in zip(statements, auth_account_ids):
            invoices = [i for i in invoice_detail_tuple if i.auth_account_id == auth_account_id]
            statement_invoices = statement_invoices + [StatementInvoicesModel(
                statement_id=statement.id,
                invoice_id=invoice.id
            ) for invoice in invoices]
        db.session.bulk_save_objects(statement_invoices)

    @classmethod
    def _clean_up_old_statements(cls, statement_settings):
        """Clean up duplicate / old statements before generating."""
        payment_account_ids = [pay_account.id for _, pay_account in statement_settings]
        payment_account_ids = select(func.unnest(cast(payment_account_ids, ARRAY(INTEGER))))
        existing_statements = db.session.query(StatementModel)\
            .filter_by(
                frequency=statement_settings[0].StatementSettings.frequency,
                from_date=cls.statement_from.date(), to_date=cls.statement_to.date(),
                is_interim_statement=False)\
            .filter(StatementModel.payment_account_id.in_(payment_account_ids))\
            .all()
        current_app.logger.debug(f'Removing {len(existing_statements)} existing duplicate/stale statement invoices.')
        remove_statements_ids = [statement.id for statement in existing_statements]
        remove_statement_invoices = db.session.query(StatementInvoicesModel)\
            .filter(StatementInvoicesModel.statement_id.in_(
                select(func.unnest(cast(remove_statements_ids, ARRAY(INTEGER))))))\
            .all()
        statement_invoice_ids = [statement_invoice.id for statement_invoice in remove_statement_invoices]
        delete_statement_invoice = delete(StatementInvoicesModel)\
            .where(StatementInvoicesModel.id.in_(select(func.unnest(cast(statement_invoice_ids, ARRAY(INTEGER))))))
        db.session.execute(delete_statement_invoice)
        db.session.flush()
        return existing_statements

    @classmethod
    def _filter_settings_by_override(cls, statement_settings, auth_account_id: str):
        """Return filtered Statement settings by payment account."""
        return [settings
                for settings in statement_settings
                if settings.PaymentAccount.auth_account_id == auth_account_id]
