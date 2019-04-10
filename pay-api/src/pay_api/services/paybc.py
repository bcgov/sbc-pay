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
from typing import Any, Dict

from pay_api.utils.enums import AuthHeaderType, ContentType

from .oauth_service import OAuthService


class PayBcService(OAuthService):
    """Service to manage PayBC communication."""

    # TODO get all these values from config map
    client_id = 'n4VoztjSBNfNWIi0Khxu1g..'
    client_secret = '2bz-Sc2q5xmUO9nUORFo6g..'
    paybc_base_url = 'https://heineken.cas.gov.bc.ca:7019/ords/cas'

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
        account = self.create_account(access_token, party)
        site = self.create_site(access_token, account, invoice_request)
        invoice = self.create_invoice(access_token, party, account, site, invoice_request)
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
            'customer_name': invoice_request.get('entity_name')
        }

        party_response = self.post(party_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, party)
        print('>Creating party Record')
        return party_response.json()

    def create_account(self, access_token, party):
        """Create account record in PayBC."""
        print('<Creating account')
        account_url = self.paybc_base_url + '/cfs/parties/{}/accs/'.format(party.get('party_number'))
        account: Dict[str, Any] = {
            'party_number': party.get('party_number'),
            'account_description': party.get('customer_name')
        }

        account_response = self.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, account)
        print('>Creating account')
        return account_response.json()

    def create_site(self, access_token, account, invoice_request):
        """Create site in PayBC."""
        print('<Creating site ')
        site_url = self.paybc_base_url + '/cfs/parties/{}/accs/{}/sites/'.format(account.get('party_number'),
                                                                                 account.get('account_number'))
        site: Dict[str, Any] = {
            'party_number': account.get('party_number'),
            'account_number': account.get('account_number'),
            'site_name': invoice_request.get('entity_name'),
            'city': invoice_request.get('city'),
            'country': invoice_request.get('country'),
            'customer_site_id': invoice_request.get('customer_site_id'),
            'address_line_1': invoice_request.get('address_line_1'),
            'postal_code': invoice_request.get('postal_code'),
            'province': invoice_request.get('province')
        }

        site_response = self.post(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, site)

        print('>Creating site ')
        return site_response.json()

    def create_contact(self, access_token, site, invoice_request):
        """Create contact in PayBC."""
        print('<Creating site contact')
        contact_url = self.paybc_base_url + '/cfs/parties/{}/accs/sites/conts/'.format(site.get('party_number'))
        contact: Dict[str, Any] = {
            'party_number': site.get('party_number'),
            'account_number': site.get('account_number'),
            'site_number': site.get('site_number'),
            'first_name': invoice_request.get('contact_first_name'),
            'last_name': invoice_request.get('contact_last_name')
        }

        contact_response = self.post(contact_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, contact)

        print('>Creating site contact')
        return contact_response.json()

    def create_invoice(self, access_token, party, account, site, invoice_request):
        """Create invoice in PayBC."""
        print('<Creating PayBC Invoice Record')
        invoice_url = self.paybc_base_url + '/cfs/parties/{}/accs/{}/{}/invs/'\
            .format(site.get('party_number'), site.get('account_number'), site.get('site_number'))
        invoice = dict(party_number=party.get('party_number'), party_name=party.get('party_name'),
                       account_number=account.get('account_number'), account_name=account.get('account_name'),
                       customer_site_id=site.get('customer_site_id'), site_number=site.get('site_number'),
                       invoice_number='TEST123', total=invoice_request.get('total'),
                       amount_due=invoice_request.get('total'), lines=[])

        for index, line_item in enumerate(invoice_request.get('lineItems')):
            invoice['lines'].append(
                {
                    'line_number': index,
                    'memo_line_name': line_item.get('name'),
                    'description': line_item.get('description'),
                    'unit_price': line_item.get('amount'),
                    'quantity': '1'
                }
            )

        invoice_response = self.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, invoice)

        print('>Creating PayBC Invoice Record')
        return invoice_response.json()
