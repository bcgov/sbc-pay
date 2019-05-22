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
from pay_api.models import Payment as PaymentModel
from pay_api.utils.errors import Error
from pay_api.models.status_code import StatusCode


class Payment():  # pylint: disable=too-many-instance-attributes
    """Service to manage Fee related operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._payment_system_code: str = None
        self._payment_method_code: str = None
        self._payment_status_code: str = None
        self._total: int = None
        self._paid: int = None
        self._created_by: str = None
        self._created_on: date = date.today()
        self._updated_by: str = None
        self._updated_on: date = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.payment_system_code: str = self._dao.payment_system_code
        self.payment_method_code: str = self._dao.payment_method_code
        self.payment_status_code: str = self._dao.payment_status_code
        self.total: int = self._dao.total
        self.paid: int = self._dao.paid
        self.created_by: str = self._dao.created_by
        self.created_on: date = self._dao.created_on
        self.updated_by: str = self._dao.updated_by
        self.updated_on: date = self._dao.updated_on

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value
        print('Setting payment id in Payment : {}'.format(value))

    @property
    def payment_system_code(self):
        """Return the payment_system_code."""
        return self._payment_system_code

    @payment_system_code.setter
    def payment_system_code(self, value: str):
        """Set the payment_system_code."""
        self._payment_system_code = value
        self._dao.payment_system_code = value

    @property
    def payment_method_code(self):
        """Return the payment_method_code."""
        return self._payment_method_code

    @payment_method_code.setter
    def payment_method_code(self, value: str):
        """Set the payment_method_code."""
        self._payment_method_code = value
        self._dao.payment_method_code = value

    @property
    def payment_status_code(self):
        """Return the payment_status_code."""
        return self._payment_status_code

    @payment_status_code.setter
    def payment_status_code(self, value: str):
        """Set the payment_status_code."""
        self._payment_status_code = value
        self._dao.payment_status_code = value

    @property
    def total(self):
        """Return the total."""
        return self._total

    @total.setter
    def total(self, value: int):
        """Set the fee_start_date."""
        self._total = value
        self._dao.total = value

    @property
    def paid(self):
        """Return the paid."""
        return self._paid

    @paid.setter
    def paid(self, value: int):
        """Set the paid."""
        self._paid = value
        self._dao.paid = value

    @property
    def created_by(self):
        """Return the created_by."""
        return self._created_by

    @created_by.setter
    def created_by(self, value: str):
        """Set the created_by."""
        self._created_by = value
        self._dao.created_by = value

    @property
    def created_on(self):
        """Return the created_on."""
        return self._created_on if self._created_on is not None else date.today()

    @created_on.setter
    def created_on(self, value: date):
        """Set the created_on."""
        self._created_on = value
        self._dao.created_on = value

    @property
    def updated_by(self):
        """Return the updated_by."""
        return self._updated_by

    @updated_by.setter
    def updated_by(self, value: str):
        """Set the created_by."""
        self._updated_by = value
        self._dao.updated_by = value

    @property
    def updated_on(self):
        """Return the updated_on."""
        return self._updated_on

    @updated_on.setter
    def updated_on(self, value: date):
        """Set the updated_on."""
        self._updated_on = value
        self._dao.updated_on = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    @staticmethod
    def create(payment_info: Dict[str, Any], fees: [Dict[str, Any]], payment_system: str = 'CC'):
        """Create payment record."""
        current_app.logger.debug('<create_payment')
        p = Payment()
        p.paid = 0
        p.payment_method_code = payment_info.get('method_of_payment', None)
        p.payment_status_code = 'DRAFT'
        p.payment_system_code = payment_system
        p.total = sum((fee.get('total')) for fee in fees)
        p.created_by = 'test'
        p.created_on = date.today()
        p.save()

        current_app.logger.debug('>create_payment')
        return p
