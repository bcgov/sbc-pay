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
from typing import Dict

from flask import current_app
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.queue_publisher import publish_response
from pay_api.utils.enums import CfsAccountStatus


class CreateAccountTask:  # pylint: disable=too-few-public-methods
    """Create CFS Account."""

    @classmethod
    def create_accounts(cls):
        """Find all pending accounts to be created in CFS.

        Steps:
        1. Find all pending CFS accounts.
        2. Create CFS accounts.
        3. Publish a message to the queue if successful.
        """
        pending_accounts = CfsAccountModel.find_all_pending_accounts()
        current_app.logger.info(f'Found {len(pending_accounts)} CFS Accounts to be created.')

        for pending_account in pending_accounts:
            # Find the payment account and create the pay system instance.
            pay_account = PaymentAccountModel.find_by_id(pending_account.account_id)
            current_app.logger.info(
                f'Creating pay system instance for {pay_account.payment_method} for account {pay_account.id}.')
            pay_system_instance = PaymentSystemFactory.create_from_payment_method(pay_account.payment_method)
            # TODO Call auth-api to get the contact details for the account.
            contact_info: Dict[str, any] = {}
            payment_info: Dict[str, any] = {
                'bankInstitutionNumber': pending_account.bank_number,
                'bankTransitNumber': pending_account.bank_branch_number,
                'bankAccountNumber': pending_account.bank_account_number,
            }
            cfs_account_details = pay_system_instance.create_account(name=pay_account.auth_account_name,
                                                                     contact_info=contact_info,
                                                                     payment_info=payment_info)

            # Update these details to cfs_account table
            pending_account.cfs_account = cfs_account_details.get('account_number')
            pending_account.cfs_site = cfs_account_details.get('site_number')
            pending_account.cfs_party = cfs_account_details.get('party_number')
            pending_account.bank_account_number = cfs_account_details.get('bank_account_number', None)
            pending_account.bank_number = cfs_account_details.get('bank_number', None)
            pending_account.bank_branch_number = cfs_account_details.get('bank_branch_number', None)
            pending_account.status.payment_instrument_number = cfs_account_details.get('payment_instrument_number',
                                                                                       None)
            pending_account.status = CfsAccountStatus.ACTIVE.value

            # TODO Populate NATS details specific to this channel
            # Publish message to the Queue, saying account has been created. Using the event spec.
            payload = {
                {
                    'specversion': '1.x-wip',
                    'type': 'bc.registry.payment.cfsAccountCreation',
                    'source': f'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/{pay_account.auth_account_id}',
                    'id': f'{pay_account.auth_account_id}',
                    'time': datetime.now(),
                    'datacontenttype': 'application/json',
                    'data': {
                        'authAccountId': pay_account.auth_account_id,
                        'status': pending_account.status
                    }
                }
            }

            try:
                publish_response(payload=payload)
            except Exception as e:  # pylint: disable=broad-except
                current_app.logger.error(e)
                current_app.logger.warning(
                    f'Notification to Queue failed, marking the Account : {pending_account.id} as PENDING',
                    e)
                pending_account.status = CfsAccountStatus.PENDING.value  # TODO for failures, what should we do ?
                pending_account.save()
