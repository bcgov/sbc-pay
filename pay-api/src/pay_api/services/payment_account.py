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

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Union, Tuple

from flask import current_app
from sentry_sdk import capture_message

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel, PaymentAccountSchema
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.services.queue_publisher import publish_response
from pay_api.utils.enums import PaymentSystem, StatementFrequency, PaymentMethod, CfsAccountStatus
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context, UserContext
from pay_api.utils.util import get_str_by_path, current_local_time, \
    get_local_formatted_date, mask


class PaymentAccount():  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment Account model related operations."""

    def __init__(self):
        """Initialize service."""
        self.__dao = None
        self._id: Union[None, int] = None
        self._auth_account_id: Union[None, str] = None
        self._auth_account_name: Union[None, str] = None
        self._payment_method: Union[None, str] = None
        self._auth_account_name: Union[None, str] = None
        self._pad_activation_date: Union[None, datetime] = None

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
        self._cfs_account_status: Union[None, str] = None

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
        self.pad_activation_date: datetime = self._dao.pad_activation_date

        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(self.id)
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
            self.cfs_account_status: str = cfs_account.status

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
    def pad_activation_date(self):
        """Return the bcol_user_id."""
        return self._pad_activation_date

    @pad_activation_date.setter
    def pad_activation_date(self, value: datetime):
        """Set the bcol_user_id."""
        self._pad_activation_date = value
        self._dao.pad_activation_date = value

    @property
    def bcol_account(self):
        """Return the bcol_account."""
        return self._bcol_account

    @bcol_account.setter
    def bcol_account(self, value: int):
        """Set the bcol_account."""
        self._bcol_account = value
        self._dao.bcol_account = value

    @property
    def cfs_account_status(self):
        """Return the cfs_account_status."""
        return self._cfs_account_status

    @cfs_account_status.setter
    def cfs_account_status(self, value: int):
        """Set the cfs_account_status."""
        self._cfs_account_status = value
        self._dao.cfs_account_status = value

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

        payment_account.publish_account_mailer_event()

        current_app.logger.debug('>create payment account')
        return payment_account

    @classmethod
    def _save_account(cls, account_request: Dict[str, any], payment_account: PaymentAccountModel):
        """Update and save payment account and CFS account model."""
        # pylint:disable=cyclic-import, import-outside-toplevel
        from pay_api.factory.payment_system_factory import PaymentSystemFactory
        # If the payment method is CC, set the payment_method as DIRECT_PAY
        payment_method: str = get_str_by_path(account_request, 'paymentInfo/methodOfPayment')
        if not payment_method or payment_method == PaymentMethod.CC.value:
            payment_method = PaymentMethod.DIRECT_PAY.value

        payment_account.payment_method = payment_method
        payment_account.auth_account_id = account_request.get('accountId')
        payment_account.auth_account_name = account_request.get('accountName', None)
        payment_account.bcol_account = account_request.get('bcolAccountNumber', None)
        payment_account.bcol_user_id = account_request.get('bcolUserId', None)
        payment_account.pad_tos_accepted_by = account_request.get('padTosAcceptedBy', None)
        payment_account.pad_tos_accepted_date = datetime.now()

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
        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id) \
            if payment_account.id else None
        pay_system = PaymentSystemFactory.create_from_payment_method(payment_method=payment_method)
        if pay_system.get_payment_system_code() == PaymentSystem.PAYBC.value:
            if cfs_account is None:
                cfs_account = pay_system.create_account(name=payment_account.auth_account_name,
                                                        contact_info=account_request.get('contactInfo'),
                                                        payment_info=account_request.get('paymentInfo'))
                if cfs_account:
                    cfs_account.payment_account = payment_account
                    cfs_account.flush()
            # If the account is PAD and bank details changed, then update bank details
            else:
                # Update details in CFS
                pay_system.update_account(name=payment_account.auth_account_name, cfs_account=cfs_account,
                                          payment_info=payment_info)

        is_pad = payment_method == PaymentMethod.PAD.value
        if is_pad:
            # override payment method for since pad has 3 days wait period
            effective_pay_method, activation_date = PaymentAccount._get_payment_based_on_pad_activation(payment_account)
            payment_account.pad_activation_date = activation_date
            payment_account.payment_method = effective_pay_method

        payment_account.save()

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
    def _get_payment_based_on_pad_activation(account: PaymentAccountModel) -> Tuple[str, str]:
        """Infer the payment method."""
        is_first_time_pad = not account.pad_activation_date
        is_unlinked_premium = not account.bcol_account
        # default it. If ever was in PAD , no new activation date needed
        if is_first_time_pad:
            new_payment_method = PaymentMethod.PAD.value if is_unlinked_premium else PaymentMethod.DRAWDOWN.value
            new_activation_date = PaymentAccount._calculate_activation_date()
        else:
            # Handle repeated changing of pad to bcol ;then to pad again etc
            new_activation_date = account.pad_activation_date  # was already in pad ;no need to extend
            is_previous_pad_activated = account.pad_activation_date < datetime.now()
            if is_previous_pad_activated:
                # was in PAD ; so no need of activation period wait time and no need to be in bcol..so use PAD again
                new_payment_method = PaymentMethod.PAD.value
            else:
                # was in pad and not yet activated ;but changed again within activation period
                new_payment_method = PaymentMethod.PAD.value if is_unlinked_premium else PaymentMethod.DRAWDOWN.value

        return new_payment_method, new_activation_date

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

    @staticmethod
    def _calculate_activation_date():
        """Find the activation date in local time.Convert it to UTC before returning."""
        account_activation_wait_period: int = current_app.config.get('PAD_CONFIRMATION_PERIOD_IN_DAYS')
        date_after_wait_period = current_local_time() + timedelta(days=account_activation_wait_period + 1)
        # reset the day to the beginning of the day.
        round_to_full_day = date_after_wait_period.replace(minute=0, hour=0, second=0)
        utc_time = round_to_full_day.astimezone(timezone.utc)
        return utc_time

    @user_context
    def asdict(self, **kwargs):
        """Return the Account as a python dict."""
        user: UserContext = kwargs['user']
        account_schema = PaymentAccountSchema()
        d = account_schema.dump(self._dao)
        # Add cfs account values based on role and payment method. For system roles, return bank details.
        if self.payment_method in (PaymentMethod.PAD.value, PaymentMethod.ONLINE_BANKING.value):
            cfs_account = {
                'cfsAccountNumber': self.cfs_account,
                'cfsPartyNumber': self.cfs_party,
                'cfsSiteNumber': self.cfs_site,
                'status': self.cfs_account_status
            }
            if user.is_system() or user.can_view_bank_info():
                mask_len = 0 if not user.can_view_bank_account_number() else current_app.config['MASK_LEN']
                cfs_account['bankAccountNumber'] = mask(self.bank_account_number, mask_len)
                cfs_account['bankInstitutionNumber'] = self.bank_number
                cfs_account['bankTransitNumber'] = self.bank_branch_number

            d['cfsAccount'] = cfs_account

        return d

    def publish_account_mailer_event(self):
        """Publish to account mailer message to send out confirmation email."""
        if self.payment_method == PaymentMethod.PAD.value:
            payload = self._create_account_event_payload('bc.registry.payment.padAccountCreate', include_pay_info=True)

            try:
                publish_response(payload=payload,
                                 client_name=current_app.config['NATS_MAILER_CLIENT_NAME'],
                                 subject=current_app.config['NATS_MAILER_SUBJECT'])
            except Exception as e:  # pylint: disable=broad-except
                current_app.logger.error(e)
                current_app.logger.error(
                    'Notification to Queue failed for the Account Mailer %s - %s', self.auth_account_id,
                    self.auth_account_name)
                capture_message(
                    'Notification to Queue failed for the Account Mailer on account creation : {msg}.'.format(
                        msg=payload), level='error')

    def _create_account_event_payload(self, event_type: str, include_pay_info: bool = False):
        """Return event payload for account."""
        payload: Dict[str, any] = {
            'specversion': '1.x-wip',
            'type': event_type,
            'source': f'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/{self.auth_account_id}',
            'id': f'{self.auth_account_id}',
            'time': f'{datetime.now()}',
            'datacontenttype': 'application/json',
            'data': {
                'accountId': self.auth_account_id,
                'accountName': self.auth_account_name,
            }
        }

        if include_pay_info:
            payload['data']['paymentInfo'] = dict(
                bankInstitutionNumber=self.bank_number,
                bankTransitNumber=self.bank_branch_number,
                bankAccountNumber=self.bank_account_number,
                paymentStartDate=get_local_formatted_date(self.pad_activation_date))
        return payload

    @staticmethod
    def unlock_frozen_accounts(account_id: int):
        """Unlock frozen accounts."""
        from pay_api.services.cfs_service import CFSService  # pylint: disable=import-outside-toplevel,cyclic-import
        pay_account: PaymentAccount = PaymentAccount.find_by_id(account_id)
        if pay_account.cfs_account_status == CfsAccountStatus.FREEZE.value:
            # update CSF
            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(pay_account.id)
            CFSService.unsuspend_cfs_account(cfs_account=cfs_account)

            cfs_account.status = CfsAccountStatus.ACTIVE.value
            cfs_account.save()

            payload = pay_account._create_account_event_payload(  # pylint:disable=protected-access
                'bc.registry.payment.unlockAccount'
            )

            try:
                publish_response(payload=payload,
                                 client_name=current_app.config['NATS_ACCOUNT_CLIENT_NAME'],
                                 subject=current_app.config['NATS_ACCOUNT_SUBJECT'])
            except Exception as e:  # pylint: disable=broad-except
                current_app.logger.error(e)
                current_app.logger.error(
                    'Notification to Queue failed for the Unlock Account %s - %s', pay_account.auth_account_id,
                    pay_account.auth_account_name)
                capture_message(
                    'Notification to Queue failed for the Unlock Account : {msg}.'.format(
                        msg=payload), level='error')
