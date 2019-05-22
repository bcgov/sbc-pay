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
"""Service to manage Payment."""

import base64
import datetime
from typing import Any, Dict

from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import AuthHeaderType, ContentType

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class PaybcMockService(PaymentSystemService, OAuthService):
    """Service to manage Payment related operations."""

    def get_payment_system_code(self):
        return 'PAYBC'

    def create_account(self, name: str, account_info: Dict[str, Any]):
        return 'P1234', 'A1234', 'S1234'

    def is_valid_account(self, party_number: str, account_number: str, site_number: str):
        return True

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_number: int):
        current_app.logger.debug('<create_invoice')

        now = datetime.datetime.now()
        curr_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        invoice = dict(
            batch_source='BC REG MANUAL_OTHER',
            cust_trx_type='BC_REG_CO_OP',
            transaction_date=curr_time,
            transaction_number=invoice_number,
            gl_date=curr_time,
            term_name='IMMEDIATE',
            comments='',
            lines=[]
        )

        for line_item in line_items:
            invoice['lines'].append(
                {
                    'line_type': 'LINE',
                    'memo_line_name': 'Test Memo Line',
                    'description': line_item.description,
                    'unit_price': line_item.total,
                    'quantity': line_item.quantity
                }
            )
        # if 1==1:
        #   raise BusinessException(Error.PAY003)
        return {"invoice_number": "10047", "pbc_ref_number": "10005", "party_number": "98545",
                "party_name": "Demo Co-Operatives", "account_name": "Demo Co-Operatives", "account_number": "4108",
                "customer_site_id": "1", "site_number": "29927", "cust_trx_type": "WTS-INVOICE-STANDARD"}

    def update_invoice(self):
        return None

    def get_receipt(self):
        return None

    def __create_party(self, access_token: str = None, party_name: str = None):
        """Create a party record in PayBC."""
        return {"party_number": "98545", "party_name": "Demo Co-Operatives"}

    def __create_paybc_account(self, access_token, party):
        """Create account record in PayBC."""

        return {"party_number": "98545", "party_name": "Demo Co-Operatives", "account_name": "Demo Co-Operatives",
                "account_number": "4108"}

    def __create_site(self, access_token, party, account, account_info):
        """Create site in PayBC."""
        current_app.logger.debug('<Creating site ')

        current_app.logger.debug('>Creating site ')
        return {"account_number": "4108", "customer_site_id": "1", "site_number": "29927"}

    def __get_token(self):
        """Generate oauth token from payBC which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('PAYBC_BASE_URL') + '/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('PAYBC_CLIENT_ID') + ':' + current_app.config.get('PAYBC_CLIENT_SECRET'),
                  'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = self.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC, ContentType.FORM_URL_ENCODED,
                                   data)
        current_app.logger.debug('>Getting token')
        return token_response
