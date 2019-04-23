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
"""Service to manage PayBC communication."""
import base64
import datetime
from typing import Any, Dict

from pay_api.utils.enums import AuthHeaderType, ContentType

import os

from .oauth_service import OAuthService


class PayBcService(OAuthService):
    """Service to manage PayBC communication."""

    # TODO get all these values from config map
    # client_id = current_app.config.get('PAYBC_CLIENT_ID') # 'n4VoztjSBNfNWIi0Khxu1g..'
    # client_secret = current_app.config.get('PAYBC_CLIENT_SECRET') # '2bz-Sc2q5xmUO9nUORFo6g..'
    # paybc_base_url = current_app.config.get('PAYBC_BASE_URL') # 'https://heineken.cas.gov.bc.ca:7019/ords/cas'

    paybc_base_url = os.getenv('PAYBC_BASE_URL')
    client_id = os.getenv('PAYBC_CLIENT_ID')
    client_secret = os.getenv('PAYBC_CLIENT_SECRET')

    def __init__(self):
        """Init."""
        super()

    def create_payment_records(self, invoice_request):
        """Create payment related records in PayBC."""
        print('<Inside create invoice')
        token_response = self.get_token()
        token_response = token_response.json()
        access_token = token_response.get('access_token')
        party = self.create_party(access_token, invoice_request)
        account = self.create_account(access_token, party, invoice_request)
        site = self.create_site(access_token, account, invoice_request)
        contact = self.create_contact(access_token, site, invoice_request)
        invoice = self.create_invoice(access_token, site, invoice_request)
        print('>Inside create invoice')
        return invoice

    def get_token(self):
        """Generate oauth token from payBC which will be used for all communication."""
        print('<Getting token')
        token_url = self.paybc_base_url + '/oauth/token'
        basic_auth_encoded = base64.b64encode(bytes(self.client_id + ':' + self.client_secret, 'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = self.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC, ContentType.FORM_URL_ENCODED,
                                   data)
        print('>Getting token')
        return token_response

    def create_party(self, access_token, invoice_request):
        """Create a party record in PayBC."""
        print('<Creating party Record')
        party_url = self.paybc_base_url + '/cfs/parties/'
        party: Dict[str, Any] = {
            'customer_name': invoice_request.get('entity_name', None)
        }

        party_response = self.post(party_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, party)
        print('>Creating party Record')
        return party_response.json()

    def create_account(self, access_token, party, invoice_request):
        """Create account record in PayBC."""
        print('<Creating account')
        account_url = self.paybc_base_url + '/cfs/parties/{}/accs/'.format(party.get('party_number'), None)
        account: Dict[str, Any] = {
            'party_number': party.get('party_number'),
            'account_description': invoice_request.get('entity_legal_name', None)
        }

        account_response = self.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, account)
        print('>Creating account')
        return account_response.json()

    def create_site(self, access_token, account, invoice_request):
        """Create site in PayBC."""
        print('<Creating site ')
        site_url = self.paybc_base_url + '/cfs/parties/{}/accs/{}/sites/'.format(account.get('party_number', None),
                                                                                 account.get('account_number', None))
        site: Dict[str, Any] = {
            'party_number': account.get('party_number', None),
            'account_number': account.get('account_number', None),
            'site_name': invoice_request.get('site_name', None),
            'city': invoice_request.get('city', None),
            'address_line_1': invoice_request.get('address_line_1', None),
            'postal_code': invoice_request.get('postal_code', None),
            'province': invoice_request.get('province', None),
            'country': invoice_request.get('country', None),
            'customer_site_id': invoice_request.get('customer_site_id', None)
        }

        site_response = self.post(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, site)

        print('>Creating site ')
        return site_response.json()

    def create_contact(self, access_token, site, invoice_request):
        """Create contact in PayBC."""
        print('<Creating site contact')
        contact_url = self.paybc_base_url + '/cfs/parties/{}/accs/{}/sites/{}/conts/'\
            .format(site.get('party_number', None), site.get('account_number', None), site.get('site_number', None))
        contact: Dict[str, Any] = {
            'party_number': site.get('party_number', None),
            'account_number': site.get('account_number', None),
            'site_number': site.get('site_number', None),
            'first_name': invoice_request.get('contact_first_name', None),
            'last_name': invoice_request.get('contact_last_name', None),
            'phone_number': invoice_request.get('contact_number', None)
        }

        contact_response = self.post(contact_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, contact)

        print('>Creating site contact')
        return contact_response.json()

    def create_invoice(self, access_token, site, invoice_request):
        """Create invoice in PayBC."""
        print('<Creating PayBC Invoice Record')
        now = datetime.datetime.now()
        curr_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        invoice_url = self.paybc_base_url + '/cfs/parties/{}/accs/{}/sites/{}/invs/'\
            .format(site.get('party_number', None), site.get('account_number', None), site.get('site_number', None))

        invoice = dict(
            batch_source=invoice_request.get('batch_source', None),
            cust_trx_type=invoice_request.get('customer_transaction_type', None),
            # bill_to_customer_number=contact.get('contact_number', None),
            # site_number=site.get('site_number', None), total=invoice_request.get('total'),
            transaction_date=curr_time,
            gl_date=curr_time,
            term_name='IMMEDIATE',
            comments=invoice_request.get('comments', None),
            lines=[]
        )

        for line_item in invoice_request.get('lineItems'):
            invoice['lines'].append(
                {
                    'line_number': line_item.get('line_number', None),
                    'line_type': line_item.get('line_type', None),
                    'memo_line_name': line_item.get('line_name', None),
                    'description': line_item.get('description', None),
                    'unit_price': line_item.get('unit_price', None),
                    'quantity': line_item.get('quantity', None)
                }
            )

        invoice_response = self.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, invoice)

        print('>Creating PayBC Invoice Record')
        return invoice_response.json()
