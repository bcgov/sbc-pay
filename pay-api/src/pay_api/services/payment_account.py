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

from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.utils.errors import Error


class PaymentAccount():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment account operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._corp_number: str = None
        self._corp_type_code: str = None
        self._payment_system_code: str = None
        self._account_number: str = None
        self._party_number: str = None
        self._site_number: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentAccountModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.corp_number: str = self._dao.corp_number
        self.corp_type_code: str = self._dao.corp_type_code
        self.payment_system_code: str = self._dao.payment_system_code
        self.account_number: str = self._dao.account_number
        self.party_number: str = self._dao.party_number
        self.site_number: str = self._dao.site_number

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
    def corp_number(self):
        """Return the corp_number."""
        return self._corp_number

    @corp_number.setter
    def corp_number(self, value: str):
        """Set the payment_id."""
        self._corp_number = value
        self._dao.corp_number = value

    @property
    def corp_type_code(self):
        """Return the corp_type_code."""
        return self._corp_type_code

    @corp_type_code.setter
    def corp_type_code(self, value: str):
        """Set the corp_type_code."""
        self._corp_type_code = value
        self._dao.corp_type_code = value

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
    def account_number(self):
        """Return the account_number."""
        return self._account_number

    @account_number.setter
    def account_number(self, value: str):
        """Set the account_number."""
        self._account_number = value
        self._dao.account_number = value

    @property
    def party_number(self):
        """Return the party_number."""
        return self._party_number

    @party_number.setter
    def party_number(self, value: str):
        """Set the party_number."""
        self._party_number = value
        self._dao.party_number = value

    @property
    def site_number(self):
        """Return the site_number."""
        return self._site_number

    @site_number.setter
    def site_number(self, value: str):
        """Set the site_number."""
        self._site_number = value
        self._dao.site_number = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the Payment Account as a python dict."""
        d = {
            'id': self._id,
            'corp_number': self._corp_number,
            'corp_type_code': self._corp_type_code,
            'payment_system_code': self._payment_system_code,
            'account_number': self._account_number,
            'party_number': self._party_number,
            'site_number': self._site_number
        }
        return d

    @staticmethod
    def create(business_info: Dict[str, Any], account_details: Tuple[str],
               payment_system: str = None):
        """Create Payment account record."""
        current_app.logger.debug('<create')
        p = PaymentAccount()
        p.corp_number = business_info.get('business_identifier', None)
        p.corp_type_code = business_info.get('corp_type', None)
        p.account_number = account_details[0]
        p.party_number = account_details[1]
        p.site_number = account_details[2]
        p.payment_system_code = payment_system

        account_dao = p.save()

        p = PaymentAccount()
        p._dao = account_dao
        current_app.logger.debug('>create')
        return p

    @classmethod
    def find_account(cls, corp_number: str,
                     corp_type: str, payment_system: str):
        """Find payment account by corp number, corp type and payment system code."""
        current_app.logger.debug('<find_payment_account')
        if not corp_number and not corp_type and not payment_system:
            raise BusinessException(Error.PAY004)

        account_dao = PaymentAccountModel.find_by_corp_number_and_corp_type_and_system(
            corp_number,
            corp_type,
            payment_system
        )
        payment_account = PaymentAccount()
        payment_account._dao = account_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_payment_account')
        return payment_account
