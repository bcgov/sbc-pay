# Copyright © 2024 Province of British Columbia
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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from cattr import Converter
from flask import current_app
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message
from sqlalchemy import and_, desc, or_

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.models import AccountFee as AccountFeeModel
from pay_api.models import AccountFeeSchema
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentAccountSchema
from pay_api.models import StatementRecipients as StatementRecipientModel
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.models import db
from pay_api.models.payment_account import PaymentAccountSearchModel
from pay_api.services import gcp_queue_publisher
from pay_api.services.auth import get_account_admin_users
from pay_api.services.cfs_service import CFSService
from pay_api.services.cfs_service import PaymentSystem as PaymentSystemService
from pay_api.services.distribution_code import DistributionCode
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.services.receipt import Receipt as ReceiptService
from pay_api.services.statement import Statement
from pay_api.services.statement_settings import StatementSettings
from pay_api.utils.constants import RECEIPT_METHOD_PAD_DAILY, RECEIPT_METHOD_PAD_STOP
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, PaymentMethod, PaymentSystem, QueueSources, StatementFrequency)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import (
    current_local_time, get_local_formatted_date, get_outstanding_txns_from_date, get_str_by_path, mask)

from .flags import flags


@dataclass
class PaymentDetails:
    """Payment details for the account."""

    account_request: Dict[str, Any] = None
    is_sandbox: bool = False
    pay_system: PaymentSystemService = None
    payment_account: PaymentAccountModel = None
    payment_info: Dict[str, Any] = None
    previous_payment: str = None


class PaymentAccount():  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment Account model related operations."""

    def __init__(self):
        """Initialize service."""
        self.__dao = None
        self.cfs_account: str = None
        self.cfs_party: str = None
        self.cfs_site: str = None
        self.bank_number: str = None
        self.bank_branch_number: str = None
        self.bank_account_number: str = None
        self.cfs_account_id: int = None
        self.cfs_account_status: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentAccountModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value: PaymentAccountModel):
        self.__dao = value
        if not hasattr(self.__dao, 'id'):
            return
        cfs_account = CfsAccountModel.find_effective_by_payment_method(self.__dao.id, self.__dao.payment_method)
        if not cfs_account:
            return
        self.cfs_account: str = cfs_account.cfs_account
        self.cfs_party: str = cfs_account.cfs_party
        self.cfs_site: str = cfs_account.cfs_site
        self.bank_number: str = cfs_account.bank_number
        self.bank_branch_number: str = cfs_account.bank_branch_number
        self.bank_account_number: str = cfs_account.bank_account_number
        self.cfs_account_id: int = cfs_account.id
        self.cfs_account_status: str = cfs_account.status

    def __getattr__(self, name):
        """Dynamic way of getting the properties from the DAO, anything not in __init__."""
        if hasattr(self._dao, name):
            return getattr(self._dao, name)
        raise AttributeError(f'Attribute {name} not found.')

    def __setattr__(self, name, value):
        """Dynamic way of setting the properties from the DAO."""
        # Prevent recursion by checking if the attribute name starts with '__' (private attribute).
        if name == '_PaymentAccount__dao':
            super().__setattr__(name, value)
        # _dao uses __dao, thus why we need to check before for __dao.
        elif hasattr(self._dao, name):
            if getattr(self._dao, name) != value:
                setattr(self._dao, name, value)
        else:
            super().__setattr__(name, value)

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
        PaymentAccount._check_and_update_statement_notifications(account)

        payment_account = PaymentAccount()
        payment_account._dao = account  # pylint: disable=protected-access

        payment_account.publish_account_mailer_event_on_creation()

        current_app.logger.debug('>create payment account')
        return payment_account

    @classmethod
    def _check_and_handle_payment_method(cls, account: PaymentAccountModel, target_payment_method: str):
        """Check if the payment method has changed and invoke handling logic."""
        if account.payment_method == target_payment_method or \
                PaymentMethod.EFT.value not in {account.payment_method, target_payment_method}:
            return

        if (account.payment_method == PaymentMethod.EFT.value and
                flags.is_on('enable-payment-change-from-eft', default=False)):
            raise BusinessException(Error.EFT_PAYMENT_ACTION_UNSUPPORTED)

        account_summary = Statement.get_summary(account.auth_account_id)
        outstanding_balance = account_summary['total_invoice_due'] + account_summary['total_due']

        if account.payment_method == PaymentMethod.EFT.value and outstanding_balance > 0:
            raise BusinessException(Error.EFT_SHORT_NAME_OUTSTANDING_BALANCE)

        # Payment method has changed between EFT and other payment methods
        statement_frequency = (
            StatementFrequency.MONTHLY.value
            if target_payment_method == PaymentMethod.EFT.value
            else StatementFrequency.default_frequency().value
        )
        Statement.generate_interim_statement(account.auth_account_id, statement_frequency)

    @classmethod
    def _check_and_update_statement_settings(cls, payment_account: PaymentAccountModel):
        """Check and update statement settings based on payment method."""
        # On create of a payment account _persist_default_statement_frequency() is used, so we
        # will only check if an update is needed if statement settings already exists - i.e an update
        if payment_account and payment_account.payment_method == PaymentMethod.EFT.value:
            # EFT payment method should automatically set statement frequency to MONTHLY
            auth_account_id = str(payment_account.auth_account_id)
            statements_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(auth_account_id)

            if statements_settings is not None and statements_settings.frequency != StatementFrequency.MONTHLY.value:
                StatementSettings.update_statement_settings(auth_account_id, StatementFrequency.MONTHLY.value)
                PaymentAccount._check_and_update_statement_notifications(payment_account)

    @classmethod
    def _check_and_update_statement_notifications(cls, payment_account: PaymentAccountModel):
        """Check and update statement notification and recipients."""
        if payment_account.payment_method != PaymentMethod.EFT.value:
            return

        # Automatically enable notifications for EFT
        payment_account.statement_notification_enabled = True
        payment_account.save()

        recipients: List[StatementRecipientModel] = StatementRecipientModel. \
            find_all_recipients_for_payment_id(payment_account.id)

        if recipients:
            return

        # Auto-populate recipients with current account admins if there are currently none
        org_admins_response = get_account_admin_users(payment_account.auth_account_id)

        members = org_admins_response.get('members') if org_admins_response.get('members', None) else []
        for member in members:
            if (user := member.get('user')) and (contacts := user.get('contacts')):
                StatementRecipientModel(
                    auth_user_id=user.get('id'),
                    firstname=user.get('firstname'),
                    lastname=user.get('lastname'),
                    email=contacts[0].get('email'),
                    payment_account_id=payment_account.id
                ).save()

    @classmethod
    def _save_account(cls, account_request: Dict[str, any], payment_account: PaymentAccountModel,
                      is_sandbox: bool = False):
        """Update and save payment account and CFS account model."""
        # pylint:disable=cyclic-import, import-outside-toplevel
        from pay_api.factory.payment_system_factory import PaymentSystemFactory

        previous_payment = payment_account.payment_method
        payment_account.auth_account_id = str(account_request.get('accountId'))

        # If the payment method is CC, set the payment_method as DIRECT_PAY
        if payment_method := get_str_by_path(account_request, 'paymentInfo/methodOfPayment'):
            if flags.is_on('enable-eft-payment-method', default=False):
                cls._check_and_handle_payment_method(payment_account, payment_method)

            payment_account.payment_method = payment_method
            payment_account.bcol_account = account_request.get('bcolAccountNumber', None)
            payment_account.bcol_user_id = account_request.get('bcolUserId', None)

        if name := account_request.get('accountName', None):
            payment_account.name = name

        if branch_name := account_request.get('branchName', None):
            payment_account.branch_name = branch_name

        if pad_tos_accepted_by := account_request.get('padTosAcceptedBy', None):
            payment_account.pad_tos_accepted_by = pad_tos_accepted_by
            payment_account.pad_tos_accepted_date = datetime.now(tz=timezone.utc)

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
        # -  If the account was on PAD and switching to EFT, and active CFS account is not present

        if payment_method:
            pay_system = PaymentSystemFactory.create_from_payment_method(payment_method=payment_method)
            details = PaymentDetails(account_request, is_sandbox, pay_system, payment_account,
                                     payment_info, previous_payment)
            cls._handle_payment_details(details)
            cls._check_and_update_statement_settings(payment_account)
        payment_account.save()

    @classmethod
    def _handle_payment_details(cls, details: PaymentDetails):
        # pylint: disable=too-many-arguments
        cfs_account = CfsAccountModel.find_effective_by_payment_method(details.payment_account.id,
                                                                       details.payment_account.payment_method) \
            if details.payment_account.id else None
        if details.pay_system.get_payment_system_code() == PaymentSystem.PAYBC.value:
            if cfs_account is None:
                cfs_account = details.pay_system.create_account(  # pylint:disable=assignment-from-none
                    identifier=details.payment_account.auth_account_id,
                    contact_info=details.account_request.get('contactInfo'),
                    payment_info=details.account_request.get('paymentInfo'),
                    payment_method=details.payment_account.payment_method)
                if cfs_account:
                    cfs_account.payment_account = details.payment_account
                    cfs_account.flush()
            else:
                details.pay_system.update_account(name=details.payment_account.name,
                                                  cfs_account=cfs_account, payment_info=details.payment_info)

            cls._update_pad_activation_date(cfs_account, details)

        # CGI is only hit for GOVM accounts, which use EJV and don't have any other payment methods for now.
        elif details.pay_system.get_payment_system_code() == PaymentSystem.CGI.value:
            # if distribution code exists, put an end date as previous day and create new.
            dist_code_svc = DistributionCode.find_active_by_account_id(details.payment_account.id)
            if dist_code_svc and dist_code_svc.distribution_code_id:
                end_date: datetime = datetime.now(tz=timezone.utc) - timedelta(days=1)
                dist_code_svc.end_date = end_date.date()
                dist_code_svc.save()

            # Create distribution code details.
            if revenue_account := details.payment_info.get('revenueAccount'):
                revenue_account.update({
                    'accountId': details.payment_account.id,
                    'name': details.payment_account.name
                })
                DistributionCode.save_or_update(revenue_account)
        else:
            if flags.is_on('multiple-payment-methods', default=False) is True:
                return
            pad_cfs_account = CfsAccountModel.find_effective_by_payment_method(details.payment_account.id or 0,
                                                                               PaymentMethod.PAD.value)
            if pad_cfs_account and pad_cfs_account.status in (CfsAccountStatus.PENDING.value,
                                                              CfsAccountStatus.PENDING_PAD_ACTIVATION):
                # If we don't set this to INACTIVE the PAD job will automatically switch our payment method for us.
                pad_cfs_account.status = CfsAccountStatus.INACTIVE.value
                pad_cfs_account.flush()

    @classmethod
    def _update_pad_activation_date(cls, cfs_account: CfsAccountModel,
                                    details: PaymentDetails):
        """Update PAD activation date."""
        is_pad = details.payment_account.payment_method == PaymentMethod.PAD.value
        # If the account is created for sandbox env, then set the status to ACTIVE and set pad activation time to now
        if is_pad and details.is_sandbox:
            cfs_account.status = CfsAccountStatus.ACTIVE.value
            details.payment_account.pad_activation_date = datetime.now(tz=timezone.utc)
        # override payment method for since pad has 3 days wait period
        elif is_pad:
            effective_pay_method, activation_date = PaymentAccount._get_payment_based_on_pad_activation(
                details.payment_account, details.previous_payment)
            details.payment_account.pad_activation_date = activation_date
            details.payment_account.payment_method = effective_pay_method

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
    def delete_account_fees(cls, auth_account_id: str):
        """Remove all account fees for the account."""
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        _ = [account_fee.delete() for account_fee in AccountFeeModel.find_by_account_id(payment_account.id)]

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

        current_app.logger.debug('>update payment account')
        return cls.find_by_id(account.id)

    @staticmethod
    def _get_payment_based_on_pad_activation(account: PaymentAccountModel, previous_payment: str) -> Tuple[str, str]:
        """Infer the payment method."""
        is_first_time_pad = not account.pad_activation_date
        # default it. If ever was in PAD , no new activation date needed
        if is_first_time_pad:
            new_payment_method = PaymentMethod.PAD.value if previous_payment is None else previous_payment
            new_activation_date = PaymentAccount._calculate_activation_date()
        else:
            # Handle repeated changing of pad to bcol ;then to pad again etc
            new_activation_date = account.pad_activation_date  # was already in pad ;no need to extend
            is_previous_pad_activated = new_activation_date < datetime.now(new_activation_date.tzinfo)
            if is_previous_pad_activated:
                # was in PAD ; so no need of activation period wait time and no need to be in BCOL/EFT..so use PAD again
                new_payment_method = PaymentMethod.PAD.value
            else:
                # was in pad and not yet activated ;but changed again within activation period
                new_payment_method = PaymentMethod.PAD.value if previous_payment is None else previous_payment

        return new_payment_method, new_activation_date

    @staticmethod
    def _persist_default_statement_frequency(payment_account_id):
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(payment_account_id)
        frequency = StatementFrequency.default_frequency().value

        # EFT Payment method default to MONTHLY frequency
        if payment_account.payment_method == PaymentMethod.EFT.value:
            frequency = StatementFrequency.MONTHLY.value

        statement_settings_model = StatementSettingsModel(
            frequency=frequency,
            payment_account_id=payment_account_id,
            # To help with mocking tests - freeze_time doesn't seem to work on the model default
            from_date=datetime.now(tz=timezone.utc).date()
        )
        statement_settings_model.save()

    @classmethod
    def find_account(cls, authorization: Dict[str, Any]) -> PaymentAccount | None:
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
        account = PaymentAccount()
        account._dao = PaymentAccountModel.find_by_id(account_id)  # pylint: disable=protected-access
        return account

    @classmethod
    def search_eft_accounts(cls, search_text: str):
        """Find EFT accounts that are in ACTIVE status (call into AUTH-API to determine)."""
        search_text = f'%{search_text}%'
        query = (
            db.session.query(PaymentAccountModel)
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id)
            .filter(and_(CfsAccountModel.payment_method == PaymentMethod.EFT.value,
                         CfsAccountModel.status.in_([CfsAccountStatus.ACTIVE.value, CfsAccountStatus.PENDING.value])))
            .filter(PaymentAccountModel.payment_method == PaymentMethod.EFT.value,
                    PaymentAccountModel.eft_enable.is_(True))
            .filter(
                and_(
                    or_(PaymentAccountModel.auth_account_id.ilike(search_text),
                        PaymentAccountModel.name.ilike(search_text),
                        and_(PaymentAccountModel.branch_name.ilike(search_text),
                             PaymentAccountModel.branch_name != '')
                        )
                ))
        )
        query = query.order_by(desc(PaymentAccountModel.auth_account_id == search_text),
                               PaymentAccountModel.id.desc()
                               )
        eft_accounts = query.limit(20).all()

        payment_accounts = [PaymentAccountSearchModel.from_row(eft_account) for eft_account in eft_accounts]
        return Converter().unstructure({'items': payment_accounts})

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
        is_cfs_payment_method = self.payment_method in (PaymentMethod.PAD.value, PaymentMethod.ONLINE_BANKING.value,
                                                        PaymentMethod.EFT.value)
        # to handle PAD 3 day period.. UI needs bank details even if PAD is not activated
        is_future_pad = (self.payment_method == PaymentMethod.DRAWDOWN.value) and (self._is_pad_in_pending_activation())
        show_cfs_details = is_cfs_payment_method or is_future_pad

        if show_cfs_details:
            # If it's PAD show future, if it's ONLINE BANKING or EFT show current.
            # Future - open this up for all payment methods, include a list.
            cfs_info = CfsAccountModel.find_effective_by_payment_method(
                self.id, PaymentMethod.PAD.value if is_future_pad else self.payment_method)
            cfs_account = {
                'cfsAccountNumber': cfs_info.cfs_account,
                'cfsPartyNumber': cfs_info.cfs_party,
                'cfsSiteNumber': cfs_info.cfs_site,
                'paymentMethod': cfs_info.payment_method,
                'status': cfs_info.status
            }
            if user.is_system() or user.can_view_bank_info():
                mask_len = 0 if not user.can_view_bank_account_number() else current_app.config['MASK_LEN']
                cfs_account['bankAccountNumber'] = mask(cfs_info.bank_account_number, mask_len)
                cfs_account['bankInstitutionNumber'] = cfs_info.bank_number
                cfs_account['bankTransitNumber'] = cfs_info.bank_branch_number

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
        if self.pad_activation_date and self.pad_activation_date > datetime.now(self.pad_activation_date.tzinfo):
            if future_cfs := CfsAccountModel.find_effective_by_payment_method(self.id, PaymentMethod.PAD.value):
                return future_cfs.status in \
                    (CfsAccountStatus.PENDING.value, CfsAccountStatus.PENDING_PAD_ACTIVATION.value)
        return False

    def publish_account_mailer_event_on_creation(self):
        """Publish to account mailer message to send out confirmation email on creation."""
        if self.payment_method == PaymentMethod.PAD.value:
            payload = self.create_account_event_payload(QueueMessageTypes.PAD_ACCOUNT_CREATE.value,
                                                        include_pay_info=True)
            self._publish_queue_message(payload, QueueMessageTypes.PAD_ACCOUNT_CREATE.value)

    def _publish_queue_message(self, payload: dict, message_type: str):
        """Publish to account mailer to send out confirmation email or notification email."""
        try:
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.PAY_API.value,
                    message_type=message_type,
                    payload=payload,
                    topic=current_app.config.get('ACCOUNT_MAILER_TOPIC')
                )
            )
        except Exception as e:  # NOQA pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.error(
                'Notification to Queue failed for the Account Mailer %s - %s', self.auth_account_id,
                self.name)
            capture_message(
                f'Notification to Queue failed for the Account Mailer : {payload}.',
                level='error')

    def create_account_event_payload(self, event_type: str, receipt_info: dict = None,
                                     include_pay_info: bool = False):
        """Return event payload for account."""
        payload: Dict[str, any] = {
            'accountId': self.auth_account_id,
            'accountName': self.name
        }

        if event_type == QueueMessageTypes.NSF_UNLOCK_ACCOUNT.value:
            payload.update({
                'invoiceNumber': receipt_info['invoiceNumber'],
                'receiptNumber': receipt_info['receiptNumber'],
                'paymentMethodDescription': receipt_info['paymentMethodDescription'],
                'invoice': receipt_info['invoice']
            })
        if event_type == QueueMessageTypes.PAD_ACCOUNT_CREATE.value:
            payload['padTosAcceptedBy'] = self.pad_tos_accepted_by
        if include_pay_info:
            payload['paymentInfo'] = {
                'bankInstitutionNumber': self.bank_number,
                'bankTransitNumber': self.bank_branch_number,
                'bankAccountNumber': mask(self.bank_account_number, current_app.config['MASK_LEN']),
                'paymentStartDate': get_local_formatted_date(self.pad_activation_date, '%B %d, %y')
            }
        return payload

    @staticmethod
    def unlock_frozen_accounts(payment_id: int, payment_account_id: int, invoice_number: str):
        """Unlock frozen accounts."""
        pay_account = PaymentAccountModel.find_by_id(payment_account_id)
        unlocked = False
        if pay_account.has_nsf_invoices:
            current_app.logger.info(f'Unlocking PAD Frozen Account {pay_account.auth_account_id}')
            cfs_account = CfsAccountModel.find_effective_by_payment_method(pay_account.id,
                                                                           PaymentMethod.PAD.value)
            CFSService.update_site_receipt_method(cfs_account, receipt_method=RECEIPT_METHOD_PAD_DAILY)
            pay_account.has_nsf_invoices = None
            pay_account.save()
            cfs_account.status = CfsAccountStatus.ACTIVE.value
            cfs_account.save()
            unlocked = True
        elif pay_account.has_overdue_invoices:
            # Reverse original invoices here, because users can still cancel out of CC payment process and pay via EFT.
            # Note we do the opposite of this in the EFT task.
            invoice_references = InvoiceReferenceModel.query \
                .filter(InvoiceReferenceModel.invoice_number == invoice_number) \
                .filter(InvoiceReferenceModel.is_consolidated.is_(False)) \
                .filter(InvoiceReferenceModel.status == InvoiceReferenceStatus.CANCELLED.value) \
                .distinct(InvoiceReferenceModel.invoice_number) \
                .all()
            # Possible some of these could already be reversed.
            for invoice_reference in invoice_references:
                try:
                    CFSService.reverse_invoice(invoice_reference.invoice_number)
                except Exception as e:  # NOQA pylint: disable=broad-except
                    current_app.logger.error(e, exc_info=True)
            current_app.logger.info(f'Unlocking EFT Frozen Account {pay_account.auth_account_id}')
            pay_account.has_overdue_invoices = None
            pay_account.save()
            unlocked = True
        if not unlocked:
            return

        receipt_info = ReceiptService.get_nsf_receipt_details(payment_id)
        pay_account_service = PaymentAccount.find_by_id(payment_account_id)
        payload = pay_account_service.create_account_event_payload(
            QueueMessageTypes.NSF_UNLOCK_ACCOUNT.value,
            receipt_info=receipt_info
        )

        try:
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.PAY_API.value,
                    message_type=QueueMessageTypes.NSF_UNLOCK_ACCOUNT.value,
                    payload=payload,
                    topic=current_app.config.get('AUTH_EVENT_TOPIC')
                )
            )
        except Exception as e:  # NOQA pylint: disable=broad-except
            current_app.logger.error(e, exc_info=True)
            current_app.logger.error(
                'Notification to Queue failed for the Unlock Account %s - %s', pay_account.auth_account_id,
                pay_account.name)
            capture_message(
                f'Notification to Queue failed for the Unlock Account : {payload}.', level='error')

    @classmethod
    def delete_account(cls, auth_account_id: str) -> PaymentAccount:
        """Delete the payment account."""
        current_app.logger.debug('<delete_account')
        pay_account = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        # 1 - Check if account have any credits
        # 2 - Check if account have any PAD/EFT transactions done in last N (10) days.
        if pay_account.credit and pay_account.credit > 0:
            raise BusinessException(Error.OUTSTANDING_CREDIT)
        cfs_account = CfsAccountModel.find_effective_by_payment_method(pay_account.id,
                                                                       PaymentMethod.PAD.value)
        # Check if PAD account is frozen.
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
                CFSService.update_site_receipt_method(cfs_account, receipt_method=RECEIPT_METHOD_PAD_STOP)
            cfs_account.save()

        # Make all other CFS accounts inactive, ONLINE BANKING, EFT etc.
        for cfs_account in CfsAccountModel.find_by_account_id(pay_account.id):
            cfs_account.status = CfsAccountStatus.INACTIVE.value
            cfs_account.save()

        if pay_account.statement_notification_enabled:
            pay_account.statement_notification_enabled = False
            pay_account.save()

    @classmethod
    def enable_eft(cls, auth_account_id: str) -> PaymentAccount:
        """Enable EFT on the payment account."""
        pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        already_has_eft_enabled = pay_account.eft_enable is True
        pay_account.eft_enable = True
        pay_account.save()
        pa_service = cls.find_by_id(pay_account.id)
        if not already_has_eft_enabled:
            payload = pa_service.create_account_event_payload(QueueMessageTypes.EFT_AVAILABLE_NOTIFICATION.value)
            pa_service._publish_queue_message(payload, QueueMessageTypes.EFT_AVAILABLE_NOTIFICATION.value)
        return pa_service
