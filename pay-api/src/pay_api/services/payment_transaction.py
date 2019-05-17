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
"""Service to manage Fee Calculation."""

from datetime import date
from typing import Dict, Any
from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.utils.errors import Error
from pay_api.models.status_code import StatusCode
from datetime import datetime

class PaymentTransaction():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment transaction operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._status_code: str = None
        self._payment_id: int = None
        self._redirect_url: str = None
        self._pay_system_url: str = None
        self._transaction_start_time:datetime = None
        self._transaction_end_time: datetime = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentTransactionModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.status_code: str = self._dao.status_code
        self.payment_id: int = self._dao.payment_id
        self.redirect_url: str = self._dao.redirect_url
        self.pay_system_url: str = self._dao.pay_system_url
        self.transaction_start_time: datetime = self._dao.transaction_start_time
        self.transaction_end_time: datetime = self._dao.transaction_end_time

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
    def status_code(self):
        """Return the status_code."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str):
        """Set the payment_id."""
        self._status_code = value
        self._dao.status_code = value

    @property
    def payment_id(self):
        """Return the payment_id."""
        return self._payment_id

    @payment_id.setter
    def payment_id(self, value: int):
        """Set the corp_type_code."""
        self._payment_id = value
        self._dao.payment_id = value

    @property
    def redirect_url(self):
        """Return the redirect_url."""
        return self._redirect_url

    @redirect_url.setter
    def redirect_url(self, value: str):
        """Set the redirect_url."""
        self._redirect_url = value
        self._dao.redirect_url = value

    @property
    def pay_system_url(self):
        """Return the pay_system_url."""
        return self._pay_system_url

    @pay_system_url.setter
    def pay_system_url(self, value: str):
        """Set the account_number."""
        self._pay_system_url = value
        self._dao.pay_system_url = value

    @property
    def transaction_start_time(self):
        """Return the transaction_start_time."""
        return self._transaction_start_time

    @transaction_start_time.setter
    def transaction_start_time(self, value: datetime):
        """Set the transaction_start_time."""
        self._transaction_start_time = value
        self._dao.transaction_start_time = value

    @property
    def transaction_end_time(self):
        """Return the transaction_end_time."""
        return self._transaction_end_time

    @transaction_end_time.setter
    def transaction_end_time(self, value: datetime):
        """Set the transaction_end_time."""
        self._transaction_end_time = value
        self._dao.transaction_end_time = value

    def save(self):
        """Save the information to the DB."""
        self._dao.save()

    @staticmethod
    def create():
        """Create Payment account record."""
        current_app.logger.debug('<create')
        p = PaymentTransaction()
        p.payment_id = None #TODO
        p.status_code = 'IN_PROGRESS'
        p.pay_system_url = None #TODO
        p.redirect_url = None #TODO
        p.transaction_start_time = datetime.now()
        p.transaction_end_time = None

        p.save()
        current_app.logger.debug('>create')
        return p
