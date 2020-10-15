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
from __future__ import annotations

from typing import Any, Dict, Union

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel, PaymentAccountSchema
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod, PaymentSystem, StatementFrequency
from pay_api.utils.errors import Error
from pay_api.utils.util import get_str_by_path


class PaymentAccount():  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment Account model related operations."""

    def __init__(self):
        """Initialize service."""
        self.__dao = None
        self._id: Union[None, int] = None
        self._auth_account_id: Union[None, str] = None
        self._auth_account_name: Union[None, str] = None
        self._payment_method: Union[None, str] = None

        self._cfs_account: Union[None, str] = None
        self._cfs_party: Union[None, str] = None
        self._cfs_site: Union[None, str] = None

        self._bank_name: Union[None, str] = None
        self._bank_number: Union[None, str] = None
        self._bank_branch: Union[None, str] = None
        self._bank_branch_number: Union[None, str] = None
        self._bank_account_number: Union[None, str] = None

        self._bcol_user_id: Union[None, str] = None
        self._bcol_account: Union[None, str] = None

        self._cfs_account_id: Union[None, int] = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentAccountModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value: PaymentAccountModel):
        self.__dao = value
        self.id: int = self._dao.id
        self.auth_account_id: str = self._dao.auth_account_id
        self.auth_account_name: str = self._dao.auth_account_name
        self.payment_method: str = self._dao.payment_method
        self.bcol_user_id: str = self._dao.bcol_user_id
        self.bcol_account: str = self._dao.bcol_account

        cfs_account: CfsAccountModel = CfsAccountModel.find_active_by_account_id(self.id)
        if cfs_account:
            self.cfs_account: str = cfs_account.cfs_account
            self.cfs_party: str = cfs_account.cfs_party
            self.cfs_site: str = cfs_account.cfs_site

            self.bank_name: str = cfs_account.bank_name
            self.bank_number: str = cfs_account.bank_number
            self.bank_branch: str = cfs_account.bank_branch
            self.bank_branch_number: str = cfs_account.bank_branch_number
            self.bank_account_number: str = cfs_account.bank_account_number
            self.cfs_account_id: int = cfs_account.id

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
    def cfs_account_id(self):
        """Return the cfs_account_id."""
        return self._cfs_account_id

    @cfs_account_id.setter
    def cfs_account_id(self, value: int):
        """Set the cfs_account_id."""
        self._cfs_account_id = value
        self._dao.cfs_account_id = value

    @property
    def auth_account_id(self):
        """Return the auth_account_id."""
        return self._auth_account_id

    @auth_account_id.setter
    def auth_account_id(self, value: str):
        """Set the auth_account_id."""
        self._auth_account_id = value
        self._dao.auth_account_id = value

    @property
    def auth_account_name(self):
        """Return the auth_account_name."""
        return self._auth_account_name

    @auth_account_name.setter
    def auth_account_name(self, value: int):
        """Set the auth_account_name."""
        self._auth_account_name = value
        self._dao.auth_account_name = value

    @property
    def payment_method(self):
        """Return the payment_method."""
        return self._payment_method

    @payment_method.setter
    def payment_method(self, value: int):
        """Set the payment_method."""
        self._payment_method = value
        self._dao.payment_method = value

    @property
    def cfs_account(self):
        """Return the cfs_account."""
        return self._cfs_account

    @cfs_account.setter
    def cfs_account(self, value: int):
        """Set the cfs_account."""
        self._cfs_account = value

    @property
    def cfs_party(self):
        """Return the cfs_party."""
        return self._cfs_party

    @cfs_party.setter
    def cfs_party(self, value: int):
        """Set the cfs_party."""
        self._cfs_party = value

    @property
    def cfs_site(self):
        """Return the cfs_site."""
        return self._cfs_site

    @cfs_site.setter
    def cfs_site(self, value: int):
        """Set the cfs_site."""
        self._cfs_site = value

    @property
    def bank_name(self):
        """Return the bank_name."""
        return self._bank_name

    @bank_name.setter
    def bank_name(self, value: int):
        """Set the bank_name."""
        self._bank_name = value

    @property
    def bank_number(self):
        """Return the bank_number."""
        return self._bank_number

    @bank_number.setter
    def bank_number(self, value: int):
        """Set the bank_number."""
        self._bank_number = value

    @property
    def bank_branch(self):
        """Return the bank_branch."""
        return self._bank_branch

    @bank_branch.setter
    def bank_branch(self, value: int):
        """Set the bank_branch."""
        self._bank_branch = value

    @property
    def bank_branch_number(self):
        """Return the bank_branch_number."""
        return self._bank_branch_number

    @bank_branch_number.setter
    def bank_branch_number(self, value: int):
        """Set the bank_branch_number."""
        self._bank_branch_number = value

    @property
    def bank_account_number(self):
        """Return the bank_account_number."""
        return self._bank_account_number

    @bank_account_number.setter
    def bank_account_number(self, value: int):
        """Set the bank_account_number."""
        self._bank_account_number = value

    @property
    def bcol_user_id(self):
        """Return the bcol_user_id."""
        return self._bcol_user_id

    @bcol_user_id.setter
    def bcol_user_id(self, value: int):
        """Set the bcol_user_id."""
        self._bcol_user_id = value
        self._dao.bcol_user_id = value

    @property
    def bcol_account(self):
        """Return the bcol_account."""
        return self._bcol_account

    @bcol_account.setter
    def bcol_account(self, value: int):
        """Set the bcol_account."""
        self._bcol_account = value
        self._dao.bcol_account = value

    @classmethod
    def create(cls, account_request: Dict[str, Any] = None) -> PaymentAccount:
        """Create new payment account record."""
        current_app.logger.debug('<create payment account')
        auth_account_id = account_request.get('accountId')
        # If an account already exists, throw error.
        if PaymentAccountModel.find_by_auth_account_id(str(auth_account_id)):
            raise BusinessException(Error.ACCOUNT_EXISTS)

        account = PaymentAccountModel()

        PaymentAccount._save_account(account_request, account)
        PaymentAccount._persist_default_statement_frequency(account.id)

        payment_account = PaymentAccount()
        payment_account._dao = account  # pylint: disable=protected-access

        current_app.logger.debug('>create payment account')
        return payment_account

    @classmethod
    def _save_account(cls, account_request: Dict[str, any], payment_account: PaymentAccountModel):
        """Update and save payment account and CFS account model."""
        # pylint:disable=cyclic-import, import-outside-toplevel
        from pay_api.factory.payment_system_factory import PaymentSystemFactory

        payment_method = payment_account.payment_method = get_str_by_path(account_request,
                                                                          'paymentInfo/methodOfPayment')
        payment_account.auth_account_id = account_request.get('accountId')
        payment_account.auth_account_name = account_request.get('accountName', None)
        payment_account.bcol_account = account_request.get('bcolAccountNumber', None)
        payment_account.bcol_user_id = account_request.get('bcolUserId', None)

        payment_info = account_request.get('paymentInfo')
        billable = payment_info.get('billable', True)
        payment_account.billable = billable

        # Steps to decide on creating CFS Account or updating CFS bank account.
        # Updating CFS account apart from bank details not in scope now.
        # Create CFS Account IF:
        # 1. New payment account
        # 2. Existing payment account:
        # -  If the account was on DIRECT_PAY and switching to Online Banking, and active CFS account is not present.
        # -  If the account was on DRAWDOWN and switching to PAD, and active CFS account is not present
        cfs_account: CfsAccountModel = CfsAccountModel.find_active_by_account_id(payment_account.id) \
            if payment_account.id else None
        pay_system = PaymentSystemFactory.create_from_payment_method(payment_method=payment_method)
        if pay_system.get_payment_system_code() == PaymentSystem.PAYBC.value:
            if cfs_account is None:
                cfs_account_details = pay_system.create_account(name=payment_account.auth_account_name,
                                                                contact_info=account_request.get('contactInfo'),
                                                                payment_info=account_request.get('paymentInfo'))
                if cfs_account_details:
                    cls._create_cfs_account(cfs_account_details, payment_account)
            # If the account is PAD and bank details changed, then update bank details
            elif payment_method == PaymentMethod.PAD.value and (
                    str(payment_info.get('bankInstitutionNumber')) != cfs_account.bank_number or
                    str(payment_info.get('bankTransitNumber')) != cfs_account.bank_branch_number or
                    str(payment_info.get('bankAccountNumber')) != cfs_account.bank_account_number):
                # Make the current CFS Account as INACTIVE in DB
                cfs_account.status = CfsAccountStatus.INACTIVE.value
                cfs_account.flush()

                cfs_details = {
                    'account_number': cfs_account.cfs_account,
                    'site_number': cfs_account.cfs_site,
                    'party_number': cfs_account.cfs_party
                }

                cfs_details.update(CFSService.update_bank_details(party_number=cfs_account.cfs_party,
                                                                  account_number=cfs_account.cfs_account,
                                                                  site_number=cfs_account.cfs_site,
                                                                  payment_info=payment_info))

                cls._create_cfs_account(cfs_details, payment_account)

        payment_account.save()
        print(payment_account.payment_method)

    @classmethod
    def _create_cfs_account(cls, cfs_account_details, payment_account):
        cfs_account = CfsAccountModel()
        cfs_account.payment_account = payment_account
        cfs_account.cfs_account = cfs_account_details.get('account_number')
        cfs_account.cfs_site = cfs_account_details.get('site_number')
        cfs_account.cfs_party = cfs_account_details.get('party_number')
        cfs_account.bank_account_number = cfs_account_details.get('bank_account_number', None)
        cfs_account.bank_number = cfs_account_details.get('bank_number', None)
        cfs_account.bank_branch_number = cfs_account_details.get('bank_branch_number', None)
        cfs_account.payment_instrument_number = cfs_account_details.get('payment_instrument_number', None)
        cfs_account.status = CfsAccountStatus.ACTIVE.value
        cfs_account.flush()
        return cfs_account

    @classmethod
    def update(cls, auth_account_id: str, account_request: Dict[str, Any]) -> PaymentAccount:
        """Create or update payment account record."""
        current_app.logger.debug('<update payment account')
        account = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        # TODO Remove it later, this is to help migration from auth to pay.
        if not account:
            return PaymentAccount.create(account_request)

        PaymentAccount._save_account(account_request, account)

        current_app.logger.debug('>create payment account')
        return cls.find_by_id(account.id)

    @staticmethod
    def _persist_default_statement_frequency(payment_account_id):
        statement_settings_model = StatementSettingsModel(
            frequency=StatementFrequency.default_frequency().value,
            payment_account_id=payment_account_id
        )
        statement_settings_model.save()

    @classmethod
    def find_account(cls, authorization: Dict[str, Any]) -> PaymentAccount:
        """Find payment account by corp number, corp type and payment system code."""
        current_app.logger.debug('<find_payment_account')
        auth_account_id: str = get_str_by_path(authorization, 'account/id')
        return PaymentAccount.find_by_auth_account_id(auth_account_id)

    @classmethod
    def find_by_auth_account_id(cls, auth_account_id: str) -> PaymentAccount:
        """Find payment account by corp number, corp type and payment system code."""
        current_app.logger.debug('<find_by_auth_account_id')
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        p = None
        if payment_account:
            p = PaymentAccount()
            p._dao = payment_account  # pylint: disable=protected-access
            current_app.logger.debug('>find_payment_account')
        return p

    @classmethod
    def find_by_id(cls, account_id: int):
        """Find pay account by id."""
        current_app.logger.debug('<find_by_id')

        account = PaymentAccount()
        account._dao = PaymentAccountModel.find_by_id(account_id)  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return account

    def asdict(self):
        """Return the Account as a python dict."""
        account_schema = PaymentAccountSchema()
        d = account_schema.dump(self._dao)
        return d
