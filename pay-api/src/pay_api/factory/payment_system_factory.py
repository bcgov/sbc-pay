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
from pay_api.utils.errors import Error
from pay_api.services.paybc_service import PaybcService
from pay_api.services.base_payment_system import PaymentSystemService


class PaymentSystemFactory:  # pylint: disable=too-few-public-methods
    """Factory to manage the creation of payment system service.

    The service instance would be an implementation of the abstract PaymentSystemService class.
    This provides flexibility for integrating multiple payment system in future.
    """

    @staticmethod
    def create(payment_method: str = None, corp_type: str = None, payment_system: str = None):
        """Create a subclass of PaymentSystemService based on input params."""
        current_app.logger.debug('<create')

        _instance: PaymentSystemService = None
        current_app.logger.debug('payment_method: {}, corp_type : {}'.format(payment_method, corp_type))
        if not payment_method and not corp_type and not payment_system:
            raise BusinessException(Error.PAY003)

        if (payment_method == 'CC' and corp_type == 'CP') or payment_system == 'PAYBC':
            _instance = PaybcService()
        else:
            raise BusinessException(Error.PAY003)

        return _instance
