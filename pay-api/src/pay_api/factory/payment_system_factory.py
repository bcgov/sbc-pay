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
"""Factory to manage creation of pay system service."""
from datetime import datetime, timezone

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.bcol_service import BcolService  # noqa: I001
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.eft_service import EftService
from pay_api.services.ejv_pay_service import EjvPayService
from pay_api.services.internal_pay_service import InternalPayService
from pay_api.services.online_banking_service import OnlineBankingService
from pay_api.services.pad_service import PadService
from pay_api.services.paybc_service import PaybcService
from pay_api.services.payment_account import PaymentAccount
from pay_api.services.wire_service import WireService
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod, Role  # noqa: I001
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context


class PaymentSystemFactory:  # pylint: disable=too-few-public-methods
    """Factory to manage the creation of payment system service.

    The service instance would be an implementation of the abstract PaymentSystemService class.
    This provides flexibility for integrating multiple payment system in future.
    """

    @staticmethod
    def create_from_payment_method(payment_method: str):
        """Create the payment system implementation from payment method."""
        _instance: PaymentSystemService = None
        if payment_method == PaymentMethod.DIRECT_PAY.value:
            _instance = DirectPayService()
        elif payment_method == PaymentMethod.CC.value:
            _instance = PaybcService()
        elif payment_method == PaymentMethod.DRAWDOWN.value:
            _instance = BcolService()
        elif payment_method == PaymentMethod.INTERNAL.value:
            _instance = InternalPayService()
        elif payment_method == PaymentMethod.ONLINE_BANKING.value:
            _instance = OnlineBankingService()
        elif payment_method == PaymentMethod.PAD.value:
            _instance = PadService()
        elif payment_method == PaymentMethod.EFT.value:
            _instance = EftService()
        elif payment_method == PaymentMethod.WIRE.value:
            _instance = WireService()
        elif payment_method == PaymentMethod.EJV.value:
            _instance = EjvPayService()

        if not _instance:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)
        return _instance

    @staticmethod
    @user_context
    def create(**kwargs):
        """Create a subclass of PaymentSystemService based on input params."""
        current_app.logger.debug('<create')
        user: UserContext = kwargs['user']
        total_fees: int = kwargs.get('fees', None)
        payment_account: PaymentAccount = kwargs.get('payment_account', None)
        payment_method = kwargs.get('payment_method', PaymentMethod.DIRECT_PAY.value)
        account_info = kwargs.get('account_info', None)
        has_bcol_account_number = account_info is not None and account_info.get('bcolAccountNumber') is not None

        _instance: PaymentSystemService = None
        current_app.logger.debug(f'payment_method: {payment_method}')

        if not payment_method:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)

        if total_fees == 0:
            _instance = InternalPayService()
        elif Role.STAFF.value in user.roles:
            if has_bcol_account_number:
                _instance = BcolService()
            else:
                _instance = InternalPayService()
        else:
            # System accounts can create BCOL payments similar to staff by providing as payload
            if has_bcol_account_number and Role.SYSTEM.value in user.roles:
                _instance = BcolService()
            else:
                _instance = PaymentSystemFactory.create_from_payment_method(payment_method)

        if not _instance:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)

        PaymentSystemFactory._validate_and_throw_error(_instance, payment_account)

        return _instance

    @staticmethod
    def _validate_and_throw_error(instance: PaymentSystemService, payment_account: PaymentAccount):
        if isinstance(instance, PadService):
            is_in_pad_confirmation_period = payment_account.pad_activation_date.replace(tzinfo=timezone.utc) > \
                datetime.now(tz=timezone.utc)
            is_cfs_account_in_pending_status = payment_account.cfs_account_status == \
                CfsAccountStatus.PENDING_PAD_ACTIVATION.value

            if is_in_pad_confirmation_period or is_cfs_account_in_pending_status:
                raise BusinessException(Error.ACCOUNT_IN_PAD_CONFIRMATION_PERIOD)
