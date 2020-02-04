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
"""Service to manage Payment Account model related operations."""

from typing import Any, Dict

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.utils.enums import PaymentSystem
from pay_api.utils.errors import Error
from pay_api.utils.util import get_str_by_path


class PaymentAccount():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment Account model related operations."""

    def __init__(self):
        """Initialize service."""
        self.__dao = None
        self._id: int = None
        self._corp_number: str = None
        self._corp_type_code: str = None
        self._payment_system_code: str = None
        self._account_number: str = None
        self._party_number: str = None
        self._site_number: str = None
        self._bcol_user_id: str = None
        self._bcol_account_id: str = None
        self._auth_account_id: str = None

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
        self.bcol_user_id: str = self._dao.bcol_user_id
        self.bcol_account_id: str = self._dao.bcol_account_id
        self.auth_account_id: str = self._dao.auth_account_id

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @property
    def corp_number(self):
        """Return the corp_number."""
        return self._corp_number

    @property
    def corp_type_code(self):
        """Return the corp_type_code."""
        return self._corp_type_code

    @property
    def payment_system_code(self):
        """Return the payment_system_code."""
        return self._payment_system_code

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @corp_number.setter
    def corp_number(self, value: str):
        """Set the payment_id."""
        self._corp_number = value
        self._dao.corp_number = value

    @corp_type_code.setter
    def corp_type_code(self, value: str):
        """Set the corp_type_code."""
        self._corp_type_code = value
        self._dao.corp_type_code = value

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

    @property
    def bcol_user_id(self):
        """Return the bcol_user_id."""
        return self._bcol_user_id

    @bcol_user_id.setter
    def bcol_user_id(self, value: str):
        """Set the bcol_user_id."""
        self._bcol_user_id = value
        self._dao.bcol_user_id = value

    @property
    def bcol_account_id(self):
        """Return the bcol_account_id."""
        return self._bcol_account_id

    @bcol_account_id.setter
    def bcol_account_id(self, value: str):
        """Set the bcol_account_id."""
        self._bcol_account_id = value
        self._dao.bcol_account_id = value

    @property
    def auth_account_id(self):
        """Return the auth_account_id."""
        return self._auth_account_id

    @auth_account_id.setter
    def auth_account_id(self, value: str):
        """Set the auth_account_id."""
        self._auth_account_id = value
        self._dao.auth_account_id = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    @staticmethod
    def create(business_info: Dict[str, Any], account_details: Dict[str, str],
               payment_system: str, authorization: Dict[str, Any]):
        """Create Payment account record."""
        current_app.logger.debug('<create')
        p = PaymentAccount()
        p.corp_number = business_info.get('businessIdentifier', None)
        p.corp_type_code = business_info.get('corpType', None)
        p.account_number = account_details.get('account_number', None)
        p.party_number = account_details.get('party_number', None)
        p.site_number = account_details.get('site_number', None)
        p.bcol_user_id = account_details.get('bcol_user_id', None)
        p.bcol_account_id = account_details.get('bcol_account_id', None)
        p.auth_account_id = get_str_by_path(authorization, 'account/id')
        p.payment_system_code = payment_system

        account_dao = p.save()

        p = PaymentAccount()
        p._dao = account_dao  # pylint: disable=protected-access
        current_app.logger.debug('>create')
        return p

    @classmethod
    def find_account(cls, business_info: Dict[str, Any],
                     authorization: Dict[str, Any], payment_system: str):
        """Find payment account by corp number, corp type and payment system code."""
        current_app.logger.debug('<find_payment_account')
        auth_account_id: str = get_str_by_path(authorization, 'account/id')
        bcol_user_id: str = get_str_by_path(authorization, 'account/paymentPreference/bcOnlineUserId')
        bcol_account_id: str = get_str_by_path(authorization, 'account/paymentPreference/bcOnlineAccountId')
        corp_number: str = business_info.get('businessIdentifier')
        corp_type: str = business_info.get('corpType')
        account_dao = None
        if payment_system == PaymentSystem.BCOL.value:
            if not bcol_user_id:
                raise BusinessException(Error.PAY015)
            account_dao = PaymentAccountModel.find_by_bcol_user_id_and_account(
                auth_account_id=auth_account_id,
                bcol_user_id=bcol_user_id,
                bcol_account_id=bcol_account_id
            )
        else:
            if not corp_number and not corp_type:
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

    @staticmethod
    def find_by_id(account_id: int):
        """Find account by id."""
        account_dao = PaymentAccountModel.find_by_id(account_id)
        if not account_dao:
            raise BusinessException(Error.PAY009)

        account = PaymentAccount()
        account._dao = account_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return account
