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
from typing import Any, Dict, Optional, Tuple

from flask import current_app
from sentry_sdk import capture_message

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.models import AccountFee as AccountFeeModel
from pay_api.models import AccountFeeSchema
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentAccountSchema
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.services.cfs_service import CFSService
from pay_api.services.distribution_code import DistributionCode
from pay_api.services.queue_publisher import publish_response
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod, PaymentSystem, StatementFrequency
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import (
    current_local_time, get_local_formatted_date, get_outstanding_txns_from_date, get_str_by_path, mask)


class PaymentAccount():  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment Account model related operations."""

    def __init__(self):
        """Initialize service."""
        self.__dao = None
        self._id: Optional[int] = None
        self._auth_account_id: Optional[str] = None
        self._name: Optional[str] = None
        self._payment_method: Optional[str] = None
        self._pad_activation_date: Optional[datetime] = None
        self._pad_tos_accepted_by: Optional[str] = None
        self._pad_tos_accepted_date: Optional[datetime] = None
        self._credit: Optional[float] = None

        self._cfs_account: Optional[str] = None
        self._cfs_party: Optional[str] = None
        self._cfs_site: Optional[str] = None

        self._bank_number: Optional[str] = None
        self._bank_branch_number: Optional[str] = None
        self._bank_account_number: Optional[str] = None

        self._bcol_user_id: Optional[str] = None
        self._bcol_account: Optional[str] = None

        self._cfs_account_id: Optional[int] = None
        self._cfs_account_status: Optional[str] = None
        self._billable: Optional[bool] = None

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
        self.name: str = self._dao.name
        self.payment_method: str = self._dao.payment_method
        self.bcol_user_id: str = self._dao.bcol_user_id
        self.bcol_account: str = self._dao.bcol_account
        self.pad_activation_date: datetime = self._dao.pad_activation_date
        self.pad_tos_accepted_by: str = self._dao.pad_tos_accepted_by
        self.pad_tos_accepted_date: datetime = self._dao.pad_tos_accepted_date
        self.credit: float = self._dao.credit
        self.billable: bool = self._dao.billable

        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(self.id)
        if cfs_account:
            self.cfs_account: str = cfs_account.cfs_account
            self.cfs_party: str = cfs_account.cfs_party
            self.cfs_site: str = cfs_account.cfs_site

            self.bank_number: str = cfs_account.bank_number
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
    def name(self):
        """Return the name."""
        return self._name

    @name.setter
    def name(self, value: str):
        """Set the name."""
        self._name = value
        self._dao.name = value

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
    def bank_number(self):
        """Return the bank_number."""
        return self._bank_number

    @bank_number.setter
    def bank_number(self, value: int):
        """Set the bank_number."""
        self._bank_number = value

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
        """Return the pad_activation_date."""
        return self._pad_activation_date

    @pad_activation_date.setter
    def pad_activation_date(self, value: datetime):
        """Set the pad_activation_date."""
        self._pad_activation_date = value
        self._dao.pad_activation_date = value

    @property
    def pad_tos_accepted_by(self):
        """Return the pad_tos_accepted_by."""
        return self._pad_tos_accepted_by

    @pad_tos_accepted_by.setter
    def pad_tos_accepted_by(self, value: datetime):
        """Set the pad_tos_accepted_by."""
        self._pad_tos_accepted_by = value
        self._dao.pad_tos_accepted_by = value

    @property
    def pad_tos_accepted_date(self):
        """Return the pad_tos_accepted_date."""
        return self._pad_tos_accepted_date

    @pad_tos_accepted_date.setter
    def pad_tos_accepted_date(self, value: datetime):
        """Set the pad_tos_accepted_by."""
        self._pad_tos_accepted_date = value
        self._dao.pad_tos_accepted_date = value

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

    @property
    def credit(self):
        """Return the credit."""
        return self._credit

    @credit.setter
    def credit(self, value: float):
        """Set the credit."""
        self._credit = value
        self._dao.credit = value

    @property
    def billable(self):
        """Return the billable."""
        return self._billable

    @billable.setter
    def billable(self, value: bool):
        """Set the billable."""
        self._billable = value
        self._dao.billable = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def flush(self):
        """Flush the information to the DB."""
        return self._dao.flush()

    @classmethod
    def create(cls, account_request: Dict[str, Any] = None, is_sandbox: bool = False) -> PaymentAccount:
        """Create new payment account record."""
        current_app.logger.debug('<create payment account')
        auth_account_id = account_request.get('accountId')
        # If an account already exists, throw error.
        if PaymentAccountModel.find_by_auth_account_id(str(auth_account_id)):
            raise BusinessException(Error.ACCOUNT_EXISTS)

        account = PaymentAccountModel()

        PaymentAccount._save_account(account_request, account, is_sandbox)
        PaymentAccount._persist_default_statement_frequency(account.id)

        payment_account = PaymentAccount()
        payment_account._dao = account  # pylint: disable=protected-access

        payment_account.publish_account_mailer_event()

        current_app.logger.debug('>create payment account')
        return payment_account

    @classmethod
    def _save_account(cls, account_request: Dict[str, any], payment_account: PaymentAccountModel,
                      is_sandbox: bool = False):
        """Update and save payment account and CFS account model."""
        # pylint:disable=cyclic-import, import-outside-toplevel
        from pay_api.factory.payment_system_factory import PaymentSystemFactory

        payment_account.auth_account_id = account_request.get('accountId')

        # If the payment method is CC, set the payment_method as DIRECT_PAY
        if payment_method := get_str_by_path(account_request, 'paymentInfo/methodOfPayment'):
            payment_account.payment_method = payment_method
            payment_account.bcol_account = account_request.get('bcolAccountNumber', None)
            payment_account.bcol_user_id = account_request.get('bcolUserId', None)

        if name := account_request.get('accountName', None):
            payment_account.name = name

        if pad_tos_accepted_by := account_request.get('padTosAcceptedBy', None):
            payment_account.pad_tos_accepted_by = pad_tos_accepted_by
            payment_account.pad_tos_accepted_date = datetime.now()

        if payment_info := account_request.get('paymentInfo'):
            billable = payment_info.get('billable', True)
            payment_account.billable = billable
        payment_account.flush()

        # Steps to decide on creating CFS Account or updating CFS bank account.
        # Updating CFS account apart from bank details not in scope now.
        # Create CFS Account IF:
        # 1. New payment account
        # 2. Existing payment account:
        # -  If the account was on DIRECT_PAY and switching to Online Banking, and active CFS account is not present.
        # -  If the account was on DRAWDOWN and switching to PAD, and active CFS account is not present

        if payment_method:
            pay_system = PaymentSystemFactory.create_from_payment_method(payment_method=payment_method)
            cls._handle_payment_details(account_request, is_sandbox, pay_system, payment_account, payment_info)
        payment_account.save()

    @classmethod
    def _handle_payment_details(cls, account_request, is_sandbox, pay_system, payment_account,
                                payment_info):
        # pylint: disable=too-many-arguments
        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id) \
            if payment_account.id else None
        if pay_system.get_payment_system_code() == PaymentSystem.PAYBC.value:
            if cfs_account is None:
                cfs_account = pay_system.create_account(  # pylint:disable=assignment-from-none
                    identifier=payment_account.auth_account_id,
                    contact_info=account_request.get('contactInfo'),
                    payment_info=account_request.get('paymentInfo'))
                if cfs_account:
                    cfs_account.payment_account = payment_account
                    cfs_account.flush()
            # If the account is PAD and bank details changed, then update bank details
            else:
                # Update details in CFS
                pay_system.update_account(name=payment_account.name, cfs_account=cfs_account, payment_info=payment_info)

            cls._update_pad_activation_date(cfs_account, is_sandbox, payment_account)

        elif pay_system.get_payment_system_code() == PaymentSystem.CGI.value:
            # if distribution code exists, put an end date as previous day and create new.
            dist_code_svc: DistributionCode = DistributionCode.find_active_by_account_id(payment_account.id)
            if dist_code_svc and dist_code_svc.distribution_code_id:
                end_date: datetime = datetime.now() - timedelta(days=1)
                dist_code_svc.end_date = end_date.date()
                dist_code_svc.save()

            # Create distribution code details.
            if revenue_account := payment_info.get('revenueAccount'):
                revenue_account.update(dict(accountId=payment_account.id,
                                            name=payment_account.name,
                                            ))
                DistributionCode.save_or_update(revenue_account)
        else:
            if cfs_account is not None:
                # if its not PAYBC ,it means switching to either drawdown or internal ,deactivate the cfs account
                cfs_account.status = CfsAccountStatus.INACTIVE.value
                cfs_account.flush()

    @classmethod
    def _update_pad_activation_date(cls, cfs_account: CfsAccountModel,
                                    is_sandbox: bool, payment_account: PaymentAccountModel):
        """Update PAD activation date."""
        is_pad = payment_account.payment_method == PaymentMethod.PAD.value
        # If the account is created for sandbox env, then set the status to ACTIVE and set pad activation time to now
        if is_pad and is_sandbox:
            cfs_account.status = CfsAccountStatus.ACTIVE.value
            payment_account.pad_activation_date = datetime.now()
        # override payment method for since pad has 3 days wait period
        elif is_pad:
            effective_pay_method, activation_date = PaymentAccount._get_payment_based_on_pad_activation(
                payment_account)
            payment_account.pad_activation_date = activation_date
            payment_account.payment_method = effective_pay_method

    @classmethod
    def save_account_fees(cls, auth_account_id: str, account_fee_request: dict):
        """Save multiple fee settings against the account."""
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        for fee in account_fee_request.get('accountFees'):
            cls._create_or_update_account_fee(fee, payment_account, fee.get('product'))
        return {
            'accountFees': AccountFeeSchema().dump(AccountFeeModel.find_by_account_id(payment_account.id), many=True)
        }

    @classmethod
    def get_account_fees(cls, auth_account_id: str):
        """Save multiple fee settings against the account."""
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        return {
            'accountFees': AccountFeeSchema().dump(AccountFeeModel.find_by_account_id(payment_account.id), many=True)
        }

    @classmethod
    def save_account_fee(cls, auth_account_id: str, product: str, account_fee_request: dict):
        """Save fee overrides against the account."""
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        cls._create_or_update_account_fee(account_fee_request, payment_account, product)
        return AccountFeeSchema().dump(AccountFeeModel.find_by_account_id_and_product(payment_account.id, product))

    @classmethod
    def _create_or_update_account_fee(cls, fee: dict, payment_account: PaymentAccountModel, product: str):
        # Save or update the fee, first lookup and see if the fees exist.
        account_fee = AccountFeeModel.find_by_account_id_and_product(
            payment_account.id, product
        )
        if not account_fee:
            account_fee = AccountFeeModel(
                account_id=payment_account.id, product=product
            )
        account_fee.apply_filing_fees = fee.get('applyFilingFees')
        account_fee.service_fee_code = fee.get('serviceFeeCode')
        account_fee.save()

    @classmethod
    def update(cls, auth_account_id: str, account_request: Dict[str, Any]) -> PaymentAccount:
        """Create or update payment account record."""
        current_app.logger.debug('<update payment account')
        try:
            account = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
            PaymentAccount._save_account(account_request, account)
        except ServiceUnavailableException as e:
            current_app.logger.error(e)
            raise

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
        is_ob_or_pad = self.payment_method in (PaymentMethod.PAD.value, PaymentMethod.ONLINE_BANKING.value)
        # to handle PAD 3 day period..UI needs bank details even if PAD is not activated
        is_future_pad = (self.payment_method == PaymentMethod.DRAWDOWN.value) and (self._is_pad_in_pending_activation())
        show_cfs_details = is_ob_or_pad or is_future_pad

        if show_cfs_details:
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

        if is_future_pad:
            d['futurePaymentMethod'] = PaymentMethod.PAD.value

        if self.payment_method == PaymentMethod.EJV.value:  # include JV details
            dist_code = DistributionCode.find_active_by_account_id(self.id)
            d['revenueAccount'] = dist_code.asdict()

        if account_fees := AccountFeeModel.find_by_account_id(self.id):
            d['accountFees'] = AccountFeeSchema().dump(account_fees, many=True)

        return d

    def _is_pad_in_pending_activation(self):
        """Find if PAD is awaiting activation."""
        return self.pad_activation_date and self.pad_activation_date > datetime.now() and self.cfs_account_status in \
            (CfsAccountStatus.PENDING.value, CfsAccountStatus.PENDING_PAD_ACTIVATION.value)

    def publish_account_mailer_event(self):
        """Publish to account mailer message to send out confirmation email."""
        if self.payment_method == PaymentMethod.PAD.value:
            payload = self._create_account_event_payload('bc.registry.payment.padAccountCreate', include_pay_info=True)

            try:
                publish_response(payload=payload,
                                 client_name=current_app.config['NATS_MAILER_CLIENT_NAME'],
                                 subject=current_app.config['NATS_MAILER_SUBJECT'])
            except Exception as e:  # NOQA pylint: disable=broad-except
                current_app.logger.error(e)
                current_app.logger.error(
                    'Notification to Queue failed for the Account Mailer %s - %s', self.auth_account_id,
                    self.name)
                capture_message(
                    f'Notification to Queue failed for the Account Mailer on account creation : {payload}.',
                    level='error')

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
                'accountName': self.name,
                'padTosAcceptedBy': self.pad_tos_accepted_by
            }
        }

        if include_pay_info:
            payload['data']['paymentInfo'] = dict(
                bankInstitutionNumber=self.bank_number,
                bankTransitNumber=self.bank_branch_number,
                bankAccountNumber=mask(self.bank_account_number, current_app.config['MASK_LEN']),
                paymentStartDate=get_local_formatted_date(self.pad_activation_date, '%B %d, %y'))
        return payload

    @staticmethod
    def unlock_frozen_accounts(account_id: int):
        """Unlock frozen accounts."""
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
            except Exception as e:  # NOQA pylint: disable=broad-except
                current_app.logger.error(e)
                current_app.logger.error(
                    'Notification to Queue failed for the Unlock Account %s - %s', pay_account.auth_account_id,
                    pay_account.name)
                capture_message(
                    f'Notification to Queue failed for the Unlock Account : {payload}.', level='error')

    @classmethod
    def delete_account(cls, auth_account_id: str) -> PaymentAccount:
        """Delete the payment account."""
        current_app.logger.debug('<delete_account')
        pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(pay_account.id)
        # 1 - Check if account have any credits
        # 2 - Check if account have any PAD transactions done in last N (10) days.
        if pay_account.credit and pay_account.credit > 0:
            raise BusinessException(Error.OUTSTANDING_CREDIT)
        # Check if account is frozen.
        cfs_status: str = cfs_account.status if cfs_account else None
        if cfs_status == CfsAccountStatus.FREEZE.value:
            raise BusinessException(Error.FROZEN_ACCOUNT)
        if InvoiceModel.find_outstanding_invoices_for_account(pay_account.id, get_outstanding_txns_from_date()):
            # Check if there is any recent PAD transactions in N days.
            raise BusinessException(Error.TRANSACTIONS_IN_PROGRESS)

        # If CFS Account present, mark it as INACTIVE.
        if cfs_status and cfs_status != CfsAccountStatus.INACTIVE.value:
            cfs_account.status = CfsAccountStatus.INACTIVE.value
            # If account is active or pending pad activation stop PAD payments.
            if pay_account.payment_method == PaymentMethod.PAD.value \
                    and cfs_status in [CfsAccountStatus.ACTIVE.value, CfsAccountStatus.PENDING_PAD_ACTIVATION.value]:
                CFSService.suspend_cfs_account(cfs_account)
            cfs_account.save()

        if pay_account.statement_notification_enabled:
            pay_account.statement_notification_enabled = False
            pay_account.save()
