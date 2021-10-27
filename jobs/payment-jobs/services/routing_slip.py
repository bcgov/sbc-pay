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
"""Task to create CFS invoices offline."""

from typing import Dict

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import CfsAccountStatus
from pay_api.utils.util import (
    get_local_formatted_date)
from sentry_sdk import capture_message


def create_cfs_account(cfs_account: CfsAccountModel, pay_account: PaymentAccountModel, auth_token: str):
    """Create CFS account for routing slip."""
    routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_payment_account_id(pay_account.id)
    try:
        # TODO add status check so that LINKED etc can be skipped.
        cfs_account_details: Dict[str, any] = CFSService.create_cfs_account(
            name=routing_slip.number,  # TODO Sending RS number as name of party
            contact_info={}
        )
        cfs_account.cfs_account = cfs_account_details.get('account_number')
        cfs_account.cfs_party = cfs_account_details.get('party_number')
        cfs_account.cfs_site = cfs_account_details.get('site_number')
        cfs_account.status = CfsAccountStatus.ACTIVE.value
        cfs_account.flush()
        # Create receipt in CFS for the payment.
        # TODO Create a receipt for the total or for one each ?
        CFSService.create_cfs_receipt(cfs_account=cfs_account,
                                      rcpt_number=routing_slip.number,
                                      rcpt_date=routing_slip.routing_slip_date.strftime('%Y-%m-%d'),
                                      amount=routing_slip.total,
                                      payment_method=pay_account.payment_method)
        return

    except Exception as e:  # NOQA # pylint: disable=broad-except

        capture_message(f'Error on creating Routing Slip CFS Account: account id={pay_account.id}, '
                        f'auth account : {pay_account.auth_account_id}, ERROR : {str(e)}', level='error')
        current_app.logger.error(e)
        cfs_account.rollback()
        return
