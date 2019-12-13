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

from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.models import Payment as PaymentModel
from pay_api.models.payment import PaymentSchema
from pay_api.services.auth import check_auth
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.enums import Status


class Payment:  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment model related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._payment_system_code: str = None
        self._payment_method_code: str = None
        self._payment_status_code: str = None
        self._invoices = None

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
        self.invoices = self._dao.invoices

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @property
    def payment_system_code(self):
        """Return the payment_system_code."""
        return self._payment_system_code

    @property
    def payment_method_code(self):
        """Return the payment_method_code."""
        return self._payment_method_code

    @payment_system_code.setter
    def payment_system_code(self, value: str):
        """Set the payment_system_code."""
        self._payment_system_code = value
        self._dao.payment_system_code = value

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

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
    def invoices(self):
        """Return the payment invoices."""
        return self._invoices

    @invoices.setter
    def invoices(self, value):
        """Set the invoices."""
        self._invoices = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the payment as a python dict."""
        payment_schema = PaymentSchema()
        d = payment_schema.dump(self._dao)

        return d

    @staticmethod
    def create(payment_info: Dict[str, Any], payment_system: str = 'CC'):
        """Create payment record."""
        current_app.logger.debug('<create_payment')
        p = Payment()
        p.payment_method_code = payment_info.get('methodOfPayment', None)
        p.payment_status_code = Status.CREATED.value
        p.payment_system_code = payment_system
        pay_dao = p.flush()
        p = Payment()
        p._dao = pay_dao  # pylint: disable=protected-access
        current_app.logger.debug('>create_payment')
        return p

    @staticmethod
    def find_by_id(identifier: int, skip_auth_check: bool = False,
                   one_of_roles: Tuple = ALL_ALLOWED_ROLES):
        """Find payment by id."""
        payment_dao = PaymentModel.find_by_id(identifier)

        # Check if user is authorized to view the payment
        if not skip_auth_check and payment_dao:
            for invoice in payment_dao.invoices:
                check_auth(invoice.account.corp_number, one_of_roles=one_of_roles)

        payment = Payment()
        payment._dao = payment_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return payment
