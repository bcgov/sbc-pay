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

from pay_api.models.bcol_payment_account import BcolPaymentAccount
from pay_api.models.internal_payment_account import InternalPaymentAccount
from pay_api.models.credit_payment_account import CreditPaymentAccount


class PaymentAccount():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment Account model related operations."""

    def __init__(self):
        """Initialize service."""
        self._id: int = None
        self._corp_number: str = None
        self._corp_type_code: str = None
        self._payment_system_code: str = None
        self._paybc_account: str = None
        self._paybc_party: str = None
        self._paybc_site: str = None
        self._bcol_user_id: str = None
        self._bcol_account_id: str = None
        self._account_id: str = None

    # @property
    # def _dao(self):
    #     if not self.__dao:
    #         self.__dao = PaymentAccountModel()
    #     return self.__dao

    # @_dao.setter
    def populate(self, value):
        if value:
            self._id: int = value.id
            if isinstance(value, BcolPaymentAccount):
                self._payment_system_code = PaymentSystem.BCOL.value
                self._bcol_account_id = value.bcol_account_id
                self._bcol_user_id = value.bcol_user_id
                self._account_id = value.account_id
            elif isinstance(value, InternalPaymentAccount):
                self._payment_system_code = PaymentSystem.INTERNAL.value
                self._corp_number = value.corp_number
                self._corp_type_code = value.corp_type_code
                self._account_id = value.account_id
            elif isinstance(value, CreditPaymentAccount):
                self._payment_system_code = PaymentSystem.PAYBC.value
                self._paybc_account = value.paybc_account
                self._paybc_party = value.paybc_party
                self._paybc_site = value.paybc_site
                self._corp_number = value.corp_number
                self._corp_type_code = value.corp_type_code
                self._account_id = value.account_id

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

    # @id.setter
    # def id(self, value: int):
    #     """Set the id."""
    #     self._id = value
    #     # self._dao.id = value

    # @corp_number.setter
    # def corp_number(self, value: str):
    #     """Set the payment_id."""
    #     self._corp_number = value
    #     # self._dao.corp_number = value

    # @corp_type_code.setter
    # def corp_type_code(self, value: str):
    #     """Set the corp_type_code."""
    #     self._corp_type_code = value
    #     # self._dao.corp_type_code = value

    # @payment_system_code.setter
    # def payment_system_code(self, value: str):
    #     """Set the payment_system_code."""
    #     self._payment_system_code = value
    #     # self._dao.payment_system_code = value

    @property
    def paybc_account(self):
        """Return the account_number."""
        return self._paybc_account

    # @paybc_account.setter
    # def paybc_account(self, value: str):
    #     """Set the account_number."""
    #     self._paybc_account = value
    #     # self._dao.account_number = value

    @property
    def paybc_party(self):
        """Return the paybc_party."""
        return self._paybc_party

    # @paybc_party.setter
    # def paybc_party(self, value: str):
    #     """Set the paybc_party."""
    #     self._paybc_party = value
    #     # self._dao.party_number = value

    @property
    def paybc_site(self):
        """Return the paybc_site."""
        return self._paybc_site

    # @paybc_site.setter
    # def paybc_site(self, value: str):
    #     """Set the paybc_site."""
    #     self._paybc_site = value
    #     # self._dao.site_number = value

    @property
    def bcol_user_id(self):
        """Return the bcol_user_id."""
        return self._bcol_user_id

    # @bcol_user_id.setter
    # def bcol_user_id(self, value: str):
    #     """Set the bcol_user_id."""
    #     self._bcol_user_id = value
    #     # self._dao.bcol_user_id = value

    @property
    def bcol_account_id(self):
        """Return the bcol_account_id."""
        return self._bcol_account_id

    # @bcol_account_id.setter
    # def bcol_account_id(self, value: str):
    #     """Set the bcol_account_id."""
    #     self._bcol_account_id = value
    #     # self._dao.bcol_account_id = value

    @property
    def account_id(self):
        """Return the account_id."""
        return self._account_id

    # @account_id.setter
    # def account_id(self, value: str):
    #     """Set the account_id."""
    #     self._account_id = value
    #     # self._dao.auth_account_id = value

    # def save(self):
    #     """Save the information to the DB."""
    #     return self._dao.save()

    @staticmethod
    def create(business_info: Dict[str, Any], account_details: Dict[str, str],
               payment_system: str, authorization: Dict[str, Any]):
        """Create Payment account record."""
        current_app.logger.debug('<create')
        auth_account_id = get_str_by_path(authorization, 'account/id')
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        if not payment_account:
            payment_account = PaymentAccountModel()
            payment_account.auth_account_id = auth_account_id
            payment_account = payment_account.save()

        dao = None
        if payment_system == PaymentSystem.BCOL.value:
            dao = BcolPaymentAccount()
            dao.account_id = payment_account.id
            dao.bcol_account_id = account_details.get('bcol_account_id', None)
            dao.bcol_user_id = account_details.get('bcol_user_id', None)
        elif payment_system == PaymentSystem.INTERNAL.value:
            dao = InternalPaymentAccount()
            dao.corp_number = business_info.get('businessIdentifier', None)
            dao.corp_type_code = business_info.get('corpType', None)
            dao.account_id = payment_account.id
        elif payment_system == PaymentSystem.PAYBC.value:
            dao = CreditPaymentAccount()
            dao.corp_number = business_info.get('businessIdentifier', None)
            dao.corp_type_code = business_info.get('corpType', None)
            dao.paybc_account = account_details.get('account_number', None)
            dao.paybc_party = account_details.get('party_number', None)
            dao.paybc_site = account_details.get('site_number', None)
            dao.account_id = payment_account.id

        dao = dao.save()

        p = PaymentAccount()
        p.populate(dao)  # pylint: disable=protected-access
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

            account_dao:BcolPaymentAccount = BcolPaymentAccount.find_by_bcol_user_id_and_account(
                auth_account_id=auth_account_id,
                bcol_user_id=bcol_user_id,
                bcol_account_id=bcol_account_id
            )
        elif payment_system == PaymentSystem.INTERNAL.value:
            account_dao:InternalPaymentAccount = InternalPaymentAccount.find_by_corp_number_and_corp_type_and_account_id(
                corp_number = corp_number,
                corp_type = corp_type,
                account_id = auth_account_id
            )
        elif payment_system == PaymentSystem.PAYBC.value:
            if not corp_number and not corp_type:
                raise BusinessException(Error.PAY004)
            account_dao = CreditPaymentAccount.find_by_corp_number_and_corp_type_and_auth_account_id(
                corp_number = corp_number,
                corp_type = corp_type,
                auth_account_id = auth_account_id
            )
        payment_account = PaymentAccount()
        payment_account.populate(account_dao) # pylint: disable=protected-access
        
        current_app.logger.debug('>find_payment_account')
        return payment_account

    @staticmethod
    def find_by_pay_system_id(**kwargs):
        """Find pay system account by id."""
        current_app.logger.debug('<find_by_pay_system_id', kwargs)
        if kwargs.get('credit_account_id'):
            account_dao = CreditPaymentAccount.find_by_id(kwargs.get('credit_account_id'))
        elif kwargs.get('internal_account_id'):
            account_dao = InternalPaymentAccount.find_by_id(kwargs.get('internal_account_id'))
        elif kwargs.get('bcol_account_id'):
            account_dao = BcolPaymentAccount.find_by_id(kwargs.get('bcol_account_id'))
        if not account_dao:
            raise BusinessException(Error.PAY009)

        account = PaymentAccount()
        account.populate(account_dao)  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_pay_system_id')
        return account
