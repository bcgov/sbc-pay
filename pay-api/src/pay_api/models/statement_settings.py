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
"""Model to handle statements data."""
from datetime import date, datetime

from sqlalchemy import ForeignKey

from pay_api.utils.enums import StatementFrequency
from pay_api.utils.util import get_local_time
from .base_model import BaseModel
from .db import db, ma
from .payment_account import PaymentAccount


class StatementSettings(BaseModel):
    """This class manages the statements settings related data."""

    __tablename__ = 'statement_settings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    frequency = db.Column(db.String(50), nullable=True, index=True)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True, index=True)
    from_date = db.Column(db.Date, default=date.today(), nullable=False)
    to_date = db.Column(db.Date, default=None, nullable=True)

    @classmethod
    def find_active_settings(cls, account_id: str, valid_date: datetime):
        """Return active statement setting for the account."""
        valid_date = get_local_time(valid_date)
        query = cls.query.join(PaymentAccount).filter(PaymentAccount.auth_account_id == account_id)
        # need this to strip of the time information from the date
        todays_datetime = datetime(valid_date.today().year, valid_date.today().month, valid_date.today().day)
        query = query.filter(StatementSettings.from_date <= todays_datetime). \
            filter((StatementSettings.to_date.is_(None)) | (StatementSettings.to_date >= todays_datetime))

        return query.one_or_none()

    @classmethod
    def find_latest_settings(cls, account_id: str):
        """Return latest active statement setting for the account."""
        query = cls.query.join(PaymentAccount).filter(PaymentAccount.auth_account_id == account_id)
        query = query.filter((StatementSettings.to_date.is_(None)))
        return query.one_or_none()

    @classmethod
    def find_accounts_settings_by_frequency(cls, valid_date: datetime, frequency: StatementFrequency):
        """Return active statement setting for the account."""
        valid_date = get_local_time(valid_date)

        query = db.session.query(StatementSettings, PaymentAccount).join(PaymentAccount)

        query = query.filter(StatementSettings.from_date <= valid_date). \
            filter((StatementSettings.to_date.is_(None)) | (StatementSettings.to_date >= valid_date)). \
            filter(StatementSettings.frequency == frequency.value)

        return query.all()


class StatementSettingsSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Statements settings."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = StatementSettings
