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

from typing import List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod
from sentry_sdk import capture_message

from utils import mailer


def create_cfs_account(cfs_account:CfsAccountModel, pay_account: PaymentAccountModel, auth_token: str):
    """Create CFS account for routing slip."""
    routing_slip = RoutingSlipModel.find_by_payment_account_id(pay_account.id)

    try:
        # TODO add status check so that LINKED etc can be skipped.
        cfs_account_details: Dict[str, any] = CFSService.create_cfs_account(
            name=rs_number,  # TODO Sending RS number as name of party
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
                                      rcpt_number=rs_number,
                                      rcpt_date=request_json.get('routingSlipDate'),
                                      amount=total,
                                      payment_method=payment_methods[0])
        return

    except Exception as e:  # NOQA # pylint: disable=broad-except

        capture_message(f'Error on creating Routing Slip CFS Account: account id={pay_account.id}, '
                        f'auth account : {pay_account.auth_account_id}, ERROR : {str(e)}', level='error')
        current_app.logger.error(e)
        pending_account.rollback()
        return