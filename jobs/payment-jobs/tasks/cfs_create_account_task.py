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
"""Task to create CFS account offline."""

from datetime import datetime
from typing import Dict, List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.cfs_service import CFSService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.constants import RECEIPT_METHOD_PAD_DAILY
from pay_api.utils.enums import AuthHeaderType, CfsAccountStatus, ContentType, PaymentMethod
from sentry_sdk import capture_message

from utils import mailer
from utils.auth import get_token


class CreateAccountTask:  # pylint: disable=too-few-public-methods
    """Create CFS Account."""

    @classmethod
    def create_accounts(cls):  # pylint: disable=too-many-locals
        """Find all pending accounts to be created in CFS.

        Steps:
        1. Find all pending CFS accounts.
        2. Create CFS accounts.
        3. Publish a message to the queue if successful.
        """
        # Pass payment method if offline account creation has be restricted based on payment method.
        pending_accounts: List[CfsAccountModel] = CfsAccountModel.find_all_pending_accounts()
        current_app.logger.info(f'Found {len(pending_accounts)} CFS Accounts to be created.')
        if len(pending_accounts) == 0:
            return

        auth_token = get_token()

        for pending_account in pending_accounts:
            # Find the payment account and create the pay system instance.
            pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(pending_account.account_id)

            # If PAD Account creation in CFS is paused, then just continue
            # TODO Remove once PAD account bugs are fixed and stable on CAS side.
            if current_app.config.get('CFS_STOP_PAD_ACCOUNT_CREATION') and \
                    pay_account.payment_method == PaymentMethod.PAD.value:
                current_app.logger.info('Continuing to next record as CFS PAD account creation is stopped.')
                continue

            current_app.logger.info(
                f'Creating pay system instance for {pay_account.payment_method} for account {pay_account.id}.')

            account_contact = cls._get_account_contact(auth_token, pay_account.auth_account_id)

            contact_info: Dict[str, str] = {
                'city': account_contact.get('city'),
                'postalCode': account_contact.get('postalCode'),
                'province': account_contact.get('region'),
                'addressLine1': account_contact.get('street'),
                'country': account_contact.get('country')
            }

            payment_info: Dict[str, any] = {
                'bankInstitutionNumber': pending_account.bank_number,
                'bankTransitNumber': pending_account.bank_branch_number,
                'bankAccountNumber': pending_account.bank_account_number,
            }

            account_name = pay_account.auth_account_name
            # For an existing CFS Account, call update.. This is to handle PAD update when CFS is offline
            try:
                if pending_account.cfs_account and pending_account.cfs_party and pending_account.cfs_site:
                    # This means, PAD account details have changed. So update banking details for this CFS account
                    bank_details = CFSService.update_bank_details(name=account_name,
                                                                  party_number=pending_account.cfs_party,
                                                                  account_number=pending_account.cfs_account,
                                                                  site_number=pending_account.cfs_site,
                                                                  payment_info=payment_info)
                    pending_account.payment_instrument_number = bank_details.get('payment_instrument_number', None)
                else:  # It's a new account, now create
                    # If the account have banking information, then create a PAD account else a regular account.
                    if pending_account.bank_number and pending_account.bank_branch_number \
                            and pending_account.bank_account_number:
                        cfs_account_details = CFSService.create_cfs_account(name=account_name,
                                                                            contact_info=contact_info,
                                                                            payment_info=payment_info,
                                                                            receipt_method=RECEIPT_METHOD_PAD_DAILY)
                    else:
                        cfs_account_details = CFSService.create_cfs_account(name=account_name,
                                                                            contact_info=contact_info,
                                                                            receipt_method=None)

                    pending_account.payment_instrument_number = cfs_account_details.get('payment_instrument_number',
                                                                                        None)
                    pending_account.cfs_account = cfs_account_details.get('account_number')
                    pending_account.cfs_site = cfs_account_details.get('site_number')
                    pending_account.cfs_party = cfs_account_details.get('party_number')

            except Exception as e:  # NOQA # pylint: disable=broad-except
                # publish to mailer queue.
                mailer.publish_mailer_events('PadSetupFailed', pay_account)
                capture_message(f'Error on creating CFS Account: account id={pay_account.id}, '
                                f'auth account : {pay_account.auth_account_id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                pending_account.rollback()
                # pending_account.status = CfsAccountStatus.INACTIVE.value
                # pending_account.save()
                continue

            # If the account has an activation time set ,
            # before that it shud be set to the  PENDING_PAD_ACTIVATION status.
            is_account_in_pad_confirmation_period = pay_account.pad_activation_date is not None and \
                pay_account.pad_activation_date > datetime.today()
            pending_account.status = CfsAccountStatus.PENDING_PAD_ACTIVATION.value if \
                is_account_in_pad_confirmation_period else CfsAccountStatus.ACTIVE.value
            pending_account.save()

    @classmethod
    def _get_account_contact(cls, auth_token: str, auth_account_id: str):
        """Return account contact by calling auth API."""
        get_contact_endpoint = current_app.config.get('AUTH_API_ENDPOINT') + f'orgs/{auth_account_id}/contacts'
        contact_response = OAuthService.get(get_contact_endpoint, auth_token, AuthHeaderType.BEARER, ContentType.JSON)
        return contact_response.json().get('contacts')[0]
