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
"""Service to manage Payment model related operations."""

from datetime import datetime
from typing import Any, Dict

from flask import current_app

from pay_api.models import Payment as PaymentModel
from pay_api.models.fee_schedule import FeeSchedule
from pay_api.utils.enums import Status


class Payment():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment model related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._payment_system_code: str = None
        self._payment_method_code: str = None
        self._payment_status_code: str = None
        self._created_by: str = None
        self._created_on: datetime = datetime.now()
        self._updated_by: str = None
        self._updated_on: datetime = None

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
        self.created_by: str = self._dao.created_by
        self.created_on: datetime = self._dao.created_on
        self.updated_by: str = self._dao.updated_by
        self.updated_on: datetime = self._dao.updated_on

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
        return self._created_on if self._created_on is not None else datetime.now()

    @created_on.setter
    def created_on(self, value: datetime):
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
    def updated_on(self, value: datetime):
        """Set the updated_on."""
        self._updated_on = value
        self._dao.updated_on = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def asdict(self):
        """Return the payment as a python dict."""
        d = {
            'id': self._id,
            'payment_system_code': self._payment_system_code,
            'payment_method_code': self._payment_method_code,
            'payment_status_code': self._payment_status_code
        }
        return d

    @staticmethod
    def create(payment_info: Dict[str, Any], current_user: str = None, payment_system: str = 'CC'):
        """Create payment record."""
        current_app.logger.debug('<create_payment')
        p = Payment()
        p.payment_method_code = payment_info.get('method_of_payment', None)
        p.payment_status_code = Status.CREATED.value
        p.payment_system_code = payment_system
        p.created_by = current_user
        p.created_on = datetime.now()
        pay_dao = p.flush()
        p = Payment()
        p._dao = pay_dao  # pylint: disable=protected-access
        current_app.logger.debug('>create_payment')
        return p

    @staticmethod
    def find_by_id(identifier: int):
        """Find payment by id."""
        payment_dao = PaymentModel.find_by_id(identifier)

        payment = Payment()
        payment._dao = payment_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return payment
