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
"""Service class to control all the operations related to statements."""
from datetime import date, datetime, timedelta

from flask import current_app

from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.models import StatementSettingsSchema as StatementSettingsModelSchema
from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel
from pay_api.utils.enums import StatementFrequency
from pay_api.utils.util import current_local_time, get_first_and_last_dates_of_month, get_week_start_and_end_date


class StatementSettings:  # pylint:disable=too-many-instance-attributes
    """Service to manage statement related operations."""

    def __init__(self):
        """Return a Statement Service Object."""
        self.__dao = None
        self._id: int = None
        self._frequency = None
        self._payment_account_id = None
        self._from_date = None
        self._to_date = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = StatementSettingsModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.frequency: str = self._dao.frequency
        self.payment_account_id: int = self._dao.payment_account_id
        self.from_date: datetime = self._dao.from_date
        self.to_date: datetime = self._dao.to_date

    @property
    def frequency(self):
        """Return the for the statement settings."""
        return self._frequency

    @frequency.setter
    def frequency(self, value: int):
        """Set the frequency for the statement settings."""
        self._frequency = value
        self._dao.frequency = value

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def from_date(self):
        """Return the from_date of the statement setting."""
        return self._from_date

    @from_date.setter
    def from_date(self, value: date):
        """Set the from for the statement setting."""
        self._from_date = value
        self._dao.from_date = value

    @property
    def payment_account_id(self):
        """Return the account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: str):
        """Set the account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def to_date(self):
        """Return the to_date of the statement setting."""
        return self._to_date

    @to_date.setter
    def to_date(self, value: date):
        """Set the to_date for the statement setting."""
        self._to_date = value
        self._dao.to_date = value

    def asdict(self):
        """Return the invoice as a python dict."""
        statements_settings_schema = StatementSettingsModelSchema()
        d = statements_settings_schema.dump(self._dao)
        return d

    @staticmethod
    def find_by_account_id(auth_account_id: str):
        """Find statements by account id."""
        current_app.logger.debug(f'<find_by_account_id {auth_account_id}')
        statements_settings = StatementSettingsModel.find_latest_settings(auth_account_id)
        if statements_settings is None:
            return None
        all_settings = []

        # iterate and find the next start date to all frequencies
        for freq in StatementFrequency:
            max_frequency = StatementSettings._find_longest_frequency(statements_settings.frequency, freq.value)
            last_date = StatementSettings._get_end_of(max_frequency)
            all_settings.append({
                'frequency': freq.name,
                'start_date': last_date + timedelta(days=1)
            })

        statements_settings_schema = StatementSettingsModelSchema()
        settings_details = {
            'current_frequency': statements_settings_schema.dump(statements_settings),
            'frequencies': all_settings
        }

        current_app.logger.debug('>statements_find_by_account_id')
        return settings_details

    @staticmethod
    def update_statement_settings(auth_account_id: str, frequency: str):
        """Update statements by account id.

        rather than checking frequency changes by individual if , it just applies the following logic.
        find the maximum frequency of current one and new one ;and calculate the date which it will keep on going.

        """
        statements_settings_schema = StatementSettingsModelSchema()
        today = datetime.today()
        current_statements_settings = StatementSettingsModel.find_active_settings(auth_account_id, today)
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        if current_statements_settings is None:
            # no frequency yet.first time accessing the statement settings.so create a new record
            statements_settings = StatementSettingsModel(frequency=frequency,
                                                         payment_account_id=payment_account.id)
            statements_settings.save()
            return statements_settings_schema.dump(statements_settings)

        # check if the latest one is the active one.. if not , inactivate the latest one.
        # this handles the case of quickly changing of frequencies..
        # changed from daily to monthly but then changed back to weekly..
        # the monthly didn't get applied ,but even before that its being changed to weekly
        future_statements_settings = StatementSettingsModel.find_latest_settings(auth_account_id)
        if future_statements_settings is not None and current_statements_settings.id != future_statements_settings.id:
            future_statements_settings.to_date = today
            future_statements_settings.save()

        max_frequency = StatementSettings._find_longest_frequency(current_statements_settings.frequency, frequency)
        last_date = StatementSettings._get_end_of(max_frequency)
        current_statements_settings.to_date = last_date  # TODO Should be date not date time?
        current_statements_settings.save()

        new_statements_settings = StatementSettingsModel(frequency=frequency,
                                                         payment_account_id=payment_account.id,
                                                         from_date=last_date + timedelta(days=1))

        new_statements_settings.save()
        return statements_settings_schema.dump(new_statements_settings)

    @staticmethod
    def _find_longest_frequency(old_frequency, new_frequency):
        """Return the longest frequency in the passed inputs."""
        freq_list = [StatementFrequency.DAILY.value,
                     StatementFrequency.WEEKLY.value,
                     StatementFrequency.MONTHLY.value]
        max_index = max(freq_list.index(old_frequency), freq_list.index(new_frequency))
        return freq_list[max_index]

    @staticmethod
    def _get_end_of(frequency: StatementFrequency):
        """Return the end of either week or month."""
        today = datetime.today()
        end_date = current_local_time()
        if frequency == StatementFrequency.WEEKLY.value:
            end_date = get_week_start_and_end_date()[1]
        if frequency == StatementFrequency.MONTHLY.value:
            end_date = get_first_and_last_dates_of_month(today.month, today.year)[1]
        return end_date
