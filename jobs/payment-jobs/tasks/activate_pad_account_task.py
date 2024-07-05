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
"""Task to activate accounts with pending activation.Mostly for PAD with 3 day activation period."""

from datetime import datetime, timedelta
from typing import List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod
from sbc_common_components.utils.enums import QueueMessageTypes

from utils import mailer


class ActivatePadAccountTask:  # pylint: disable=too-few-public-methods
    """Activate a PAD account after confirmation period."""

    @classmethod
    def activate_pad_accounts(cls):
        """Find all accounts with pending account activation status.

        Steps:
        1. Find all accounts with pending PAD account activation status.
        2. Activate them.
        """
        pending_pad_activation_accounts = CfsAccountModel.find_all_accounts_with_status(
            status=CfsAccountStatus.PENDING_PAD_ACTIVATION.value)
        current_app.logger.info(
            f'Found {len(pending_pad_activation_accounts)} CFS Accounts to be pending PAD activation.')
        if len(pending_pad_activation_accounts) == 0:
            return

        for pending_account in pending_pad_activation_accounts:
            pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(pending_account.account_id)

            # check is still in the pad activation period
            is_activation_period_over = pay_account.pad_activation_date - timedelta(hours=1) < datetime.now()
            current_app.logger.info(
                f'Account {pay_account.id} ready for activation:{is_activation_period_over}')

            if is_activation_period_over:
                pending_account.status = CfsAccountStatus.ACTIVE.value
                pending_account.save()
                # If account was in another payment method, update it to pad
                if pay_account.payment_method != PaymentMethod.PAD.value:
                    pay_account.payment_method = PaymentMethod.PAD.value
                    pay_account.save()
                mailer.publish_mailer_events(QueueMessageTypes.CONFIRMATION_PERIOD_OVER.value, pay_account)
