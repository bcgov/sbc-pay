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
"""Service to manage PayBC interaction."""

from typing import Any, Dict, Tuple

import zeep
from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentSystem
from pay_api.utils.errors import Error

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class BcolService(PaymentSystemService, OAuthService):
    """Service to manage BCOL integration."""

    query_profile_client = None
    auth_code_mapping = {
        'G': 'GDSA',
        'M': 'Master',
        'O': 'Office',
        'P': 'Prime',
        'C': 'Contact',
        '': 'Ordinary'
    }
    account_type_mapping = {
        'B': 'Billable',
        'N': 'Non-Billable',
        'I': 'Internal'
    }
    tax_status_mapping = {
        'E': 'Exempt',
        'Z': 'Zero-rate',
        '': 'Must-Pay'
    }
    status_mapping = {
        'Y': 'Granted',
        'N': 'Revoked'
    }

    def create_account(self, name: str, account_info: Dict[str, Any]):
        """Create account."""
        current_app.logger.debug('<create_account')

    def get_payment_system_url(self, invoice: Invoice, return_url: str):
        """Return the payment system url."""
        current_app.logger.debug('<get_payment_system_url')

        current_app.logger.debug('>get_payment_system_url')

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.BCOL.value

    def query_profile(self, account_id: str, bcol_user_id: str):  # pragma: no cover
        """Query for profile and return the results."""
        current_app.logger.debug('<query_profile')
        if not self.query_profile_client:
            self.query_profile_client = zeep.Client(current_app.config.get('BCOL_QUERY_PROFILE_WSDL_URL'))
        # Call the query profile service to fetch profile
        data = {
            'Version': current_app.config.get('BCOL_DEBIT_ACCOUNT_VERSION'),
            'Userid': bcol_user_id,  # 'pc25020',
            'linkcode': current_app.config.get('BCOL_LINK_CODE')
        }
        try:
            profile_resp = zeep.helpers.serialize_object(self.query_profile_client.service.queryProfile(req=data))
            current_app.logger.debug('--' + self._get(profile_resp, 'AccountNumber') + '--')
            current_app.logger.debug('--' + account_id + '--')
            if self._get(profile_resp, 'AccountNumber') != account_id:
                current_app.logger.error('Account Number doesnt match')
                raise BusinessException(Error.PAY020)

            response = {
                'userId': self._get(profile_resp, 'Userid'),
                'accountNumber': self._get(profile_resp, 'AccountNumber'),
                'authCode': self._get(profile_resp, 'AuthCode'),
                'authCodeDesc': self.auth_code_mapping[self._get(profile_resp, 'AuthCode')],
                'accountType': self._get(profile_resp, 'AccountType'),
                'accountTypeDesc': self.account_type_mapping[self._get(profile_resp, 'AccountType')],
                'gstStatus': self._get(profile_resp, 'GSTStatus'),
                'gstStatusDesc': self.tax_status_mapping[self._get(profile_resp, 'GSTStatus')],
                'pstStatus': self._get(profile_resp, 'PSTStatus'),
                'pstStatusDesc': self.tax_status_mapping[self._get(profile_resp, 'PSTStatus')],
                'userName': self._get(profile_resp, 'UserName'),
                'orgName': self._get(profile_resp, 'org-name'),
                'orgType': self._get(profile_resp, 'org-type'),
                'phone': self._get(profile_resp, 'UserPhone'),
                'fax': self._get(profile_resp, 'UserFax')
            }
            address = profile_resp['Address']
            if address:
                response['address'] = {
                    'line1': self._get(address, 'AddressA'),
                    'line2': self._get(address, 'AddressB'),
                    'city': self._get(address, 'City'),
                    'province': self._get(address, 'Prov'),
                    'country': self._get(address, 'Country'),
                    'postalCode': self._get(address, 'PostalCode')
                }
            query_profile_flags = profile_resp['queryProfileFlag']
            if query_profile_flags:
                flags: str = ''
                for flag in query_profile_flags:
                    flags += ',' + flag['name']
                response['profile_flags'] = flags
        except BusinessException as e:
            current_app.logger.error(e)
            raise
        except Exception as e:
            current_app.logger.error(e)
            raise BusinessException(Error.PAY999)

        current_app.logger.debug(response)

        current_app.logger.debug('>query_profile')
        return response

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_number: int):
        """Create Invoice in PayBC."""
        current_app.logger.debug('<create_invoice')

        current_app.logger.debug('>create_invoice')

    def update_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice."""
        current_app.logger.debug('<update_invoice')

    def cancel_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug('<cancel_invoice')

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_number: str):
        """Get receipt from bcol for the receipt number or get receipt against invoice number."""
        current_app.logger.debug('<get_receipt')

    @staticmethod
    def _get(value: object, key: object) -> str:  # pragma: no cover
        """Get the value from dict and strip."""
        if value[key]:
            return value[key].strip()
        return None
