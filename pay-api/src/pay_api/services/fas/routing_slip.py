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
"""Service to manage routing slip operations."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict

from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import RoutingSlipSchema


class RoutingSlip:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Routing slip related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._number: str = None
        self._payment_account_id: int = None
        self._status_code: str = None
        self._total: Decimal = None
        self._remaining_amount: Decimal = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = RoutingSlipModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao: RoutingSlipModel = value
        self.id: int = self._dao.id
        self.number: str = self._dao.number
        self.status_code: str = self._dao.status_code
        self.payment_account_id: int = self._dao.payment_account_id
        self.total: Decimal = self._dao.total
        self.remaining_amount: Decimal = self._dao.remaining_amount

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
    def number(self):
        """Return the number."""
        return self._number

    @number.setter
    def number(self, value: str):
        """Set the number."""
        self._number = value
        self._dao.number = value

    @property
    def status_code(self):
        """Return the status_code."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str):
        """Set the status_code."""
        self._status_code = value
        self._dao.status_code = value

    @property
    def payment_account_id(self):
        """Return the payment_account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: int):
        """Set the payment_account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def total(self):
        """Return the total."""
        return self._total

    @total.setter
    def total(self, value: Decimal):
        """Set the total."""
        self._total = value
        self._dao.total = value

    @property
    def remaining_amount(self):
        """Return the remaining_amount."""
        return self._remaining_amount

    @remaining_amount.setter
    def remaining_amount(self, value: Decimal):
        """Set the amount."""
        self._remaining_amount = value
        self._dao.remaining_amount = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self) -> Dict[str]:
        """Return the routing slip as a python dict."""
        routing_slip_schema = RoutingSlipSchema()
        d = routing_slip_schema.dump(self._dao)
        return d

    @classmethod
    def search(cls, **kwargs):
        """Search for routing slip."""
        # Do nothing for now

    @classmethod
    def create(cls, request_json: Dict[str, any]):
        """Search for routing slip."""
        # Do nothing for now
