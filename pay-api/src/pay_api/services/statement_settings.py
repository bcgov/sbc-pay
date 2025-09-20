# Copyright © 2024 Province of British Columbia
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
"""Service class to control all the operations related to statements."""
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import exists

from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.models import StatementSettingsSchema as StatementSettingsModelSchema
from pay_api.models import db
from pay_api.services import ActivityLogPublisher
from pay_api.utils.dataclasses import StatementIntervalChangeEvent
from pay_api.utils.enums import QueueSources, StatementFrequency
from pay_api.utils.util import current_local_time, get_first_and_last_dates_of_month, get_week_start_and_end_date


class StatementSettings:
    """Service to manage statement related operations."""

    @staticmethod
    def find_by_account_id(auth_account_id: str):
        """Find statements by account id."""
        current_app.logger.debug(f"<find_by_account_id {auth_account_id}")
        statements_settings = StatementSettingsModel.find_latest_settings(auth_account_id)
        if statements_settings is None:
            return None
        all_settings = []

        # iterate and find the next start date to all frequencies
        for freq in StatementFrequency:
            max_frequency = StatementSettings._find_longest_frequency(statements_settings.frequency, freq.value)
            last_date = StatementSettings._get_end_of(max_frequency)
            all_settings.append({"frequency": freq.name, "start_date": last_date + timedelta(days=1)})

        statements_settings_schema = StatementSettingsModelSchema()
        settings_details = {
            "current_frequency": statements_settings_schema.dump(statements_settings),
            "frequencies": all_settings,
        }

        current_app.logger.debug(">statements_find_by_account_id")
        return settings_details

    @staticmethod
    def update_statement_settings(auth_account_id: str, frequency: str):
        """Update statements by account id.

        rather than checking frequency changes by individual if , it just applies the following logic.
        find the maximum frequency of current one and new one ;and calculate the date which it will keep on going.

        """
        statements_settings_schema = StatementSettingsModelSchema()
        today = datetime.now(tz=timezone.utc)
        current_statements_settings = StatementSettingsModel.find_active_settings(auth_account_id, today)
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)

        old_frequency = None
        if current_statements_settings is None:
            # no frequency yet.first time accessing the statement settings.so create a new record
            statements_settings = StatementSettingsModel(frequency=frequency, payment_account_id=payment_account.id)
            statements_settings.save()

            ActivityLogPublisher.publish_statement_interval_change_event(
                StatementIntervalChangeEvent(
                    account_id=payment_account.auth_account_id,
                    old_frequency=old_frequency,
                    new_frequency=frequency,
                    source=QueueSources.PAY_API.value,
                )
            )

            return statements_settings_schema.dump(statements_settings)

        # check if the latest one is the active one.. if not , inactivate the latest one.
        # this handles the case of quickly changing of frequencies..
        # changed from daily to monthly but then changed back to weekly..
        # the monthly didn't get applied ,but even before that its being changed to weekly
        future_statements_settings = StatementSettingsModel.find_latest_settings(auth_account_id)
        if future_statements_settings is not None and current_statements_settings.id != future_statements_settings.id:
            future_statements_settings.to_date = today
            future_statements_settings.save()

        old_frequency = current_statements_settings.frequency
        max_frequency = StatementSettings._find_longest_frequency(current_statements_settings.frequency, frequency)
        last_date = StatementSettings._get_end_of(max_frequency)
        current_statements_settings.to_date = last_date
        current_statements_settings.save()

        new_statements_settings = StatementSettingsModel(
            frequency=frequency,
            payment_account_id=payment_account.id,
            from_date=last_date + timedelta(days=1),
        )

        new_statements_settings.save()

        if old_frequency != frequency:
            ActivityLogPublisher.publish_statement_interval_change_event(
                StatementIntervalChangeEvent(
                    account_id=payment_account.auth_account_id,
                    old_frequency=old_frequency,
                    new_frequency=frequency,
                    source=QueueSources.PAY_API.value,
                )
            )

        return statements_settings_schema.dump(new_statements_settings)

    @staticmethod
    def _find_longest_frequency(old_frequency, new_frequency):
        """Return the longest frequency in the passed inputs."""
        freq_list = [
            StatementFrequency.DAILY.value,
            StatementFrequency.WEEKLY.value,
            StatementFrequency.MONTHLY.value,
        ]
        max_index = max(freq_list.index(old_frequency), freq_list.index(new_frequency))
        return freq_list[max_index]

    @staticmethod
    def _get_end_of(frequency: StatementFrequency):
        """Return the end of either week or month."""
        today = datetime.now(tz=timezone.utc)
        end_date = current_local_time()
        if frequency == StatementFrequency.WEEKLY.value:
            end_date = get_week_start_and_end_date()[1]
        if frequency == StatementFrequency.MONTHLY.value:
            end_date = get_first_and_last_dates_of_month(today.month, today.year)[1]
        return end_date

    @classmethod
    def find_accounts_settings_by_frequency(
        cls,
        valid_date: datetime,
        frequency: StatementFrequency,
        from_date=None,
        to_date=None,
    ):
        """Return active statement setting for the account."""
        valid_date = valid_date.date()
        query = db.session.query(StatementSettingsModel, PaymentAccountModel).join(PaymentAccountModel)
        query = (
            query.filter(StatementSettingsModel.from_date <= valid_date)
            .filter((StatementSettingsModel.to_date.is_(None)) | (StatementSettingsModel.to_date >= valid_date))
            .filter(StatementSettingsModel.frequency == frequency.value)
        )

        if from_date and to_date:
            query = query.filter(StatementSettingsModel.to_date == to_date)
            query = query.filter(
                ~exists()
                .where(StatementModel.from_date <= from_date)
                .where(StatementModel.to_date >= to_date)
                .where(StatementModel.is_interim_statement.is_(True))
                .where(StatementModel.payment_account_id == StatementSettingsModel.payment_account_id)
            )
        return query.all()
