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
"""Factory to manage creation of pay system service."""

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.bcol_service import BcolService  # noqa: I001
from pay_api.services.internal_pay_service import InternalPayService
from pay_api.services.paybc_service import PaybcService
from pay_api.utils.enums import PaymentSystem, Role  # noqa: I001
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context


class PaymentSystemFactory:  # pylint: disable=too-few-public-methods
    """Factory to manage the creation of payment system service.

    The service instance would be an implementation of the abstract PaymentSystemService class.
    This provides flexibility for integrating multiple payment system in future.
    """

    @staticmethod
    def create_from_system_code(payment_system: str):
        """Create the payment system implementation from the payment system code."""
        _instance: PaymentSystemService = None
        if payment_system == PaymentSystem.PAYBC.value:
            _instance = PaybcService()
        elif payment_system == PaymentSystem.BCOL.value:
            _instance = BcolService()
        elif payment_system == PaymentSystem.INTERNAL.value:
            _instance = InternalPayService()
        if not _instance:
            raise BusinessException(Error.PAY003)
        return _instance

    @staticmethod
    @user_context
    def create(**kwargs):
        """Create a subclass of PaymentSystemService based on input params."""
        current_app.logger.debug('<create')
        user: UserContext = kwargs['user']
        total_fees: int = kwargs.get('fees', None)
        payment_method = kwargs.get('payment_method', 'CC')

        _instance: PaymentSystemService = None
        current_app.logger.debug('payment_method: {}'.format(payment_method))

        if not payment_method:
            raise BusinessException(Error.PAY003)

        if total_fees == 0 or (Role.STAFF.value in user.roles and payment_method != 'DRAWDOWN'):
            _instance = InternalPayService()
        else:
            if payment_method == 'CC':
                _instance = PaybcService()
            elif payment_method == 'DRAWDOWN':
                _instance = BcolService()

        if not _instance:
            raise BusinessException(Error.PAY003)

        return _instance
