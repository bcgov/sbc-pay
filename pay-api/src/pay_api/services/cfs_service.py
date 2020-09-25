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
"""Service to invoke CFS related operations."""
import base64
import re
from typing import Dict, Any

from flask import current_app
from requests import HTTPError

from pay_api.services.oauth_service import OAuthService
from pay_api.utils.constants import (
    DEFAULT_ADDRESS_LINE_1, DEFAULT_CITY, DEFAULT_COUNTRY, DEFAULT_JURISDICTION, DEFAULT_POSTAL_CODE)
from pay_api.utils.enums import AuthHeaderType, ContentType


class CFSService(OAuthService):
    """Service to invoke CFS related operations."""

    @staticmethod
    def create_cfs_account(name: str, contact_info: Dict[str, Any]):
        """Create a cfs account and return the details."""
        name = re.sub(r'[^a-zA-Z0-9]+', ' ', name)
        access_token = CFSService.get_token().json().get('access_token')
        party = CFSService._create_party(access_token, name)
        account = CFSService._create_paybc_account(access_token, party)
        site = CFSService._create_site(access_token, party, account, contact_info)
        return {
            'party_number': party.get('party_number'),
            'account_number': account.get('account_number'),
            'site_number': site.get('site_number')
        }

    @staticmethod
    def _create_party(access_token: str = None, party_name: str = None):
        """Create a party record in PayBC."""
        current_app.logger.debug('<Creating party Record')
        party_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/'
        party: Dict[str, Any] = {
            'customer_name': party_name
        }

        party_response = OAuthService.post(party_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, party)
        current_app.logger.debug('>Creating party Record')
        return party_response.json()

    @staticmethod
    def _create_paybc_account(access_token, party):
        """Create account record in PayBC."""
        current_app.logger.debug('<Creating account')
        account_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/'.format(
            party.get('party_number', None))
        account: Dict[str, Any] = {
            'party_number': party.get('party_number'),
            'account_description': party.get('customer_name')[:30]
        }

        account_response = OAuthService.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                             account)
        current_app.logger.debug('>Creating account')
        return account_response.json()

    @staticmethod
    def _create_site(access_token, party, account, contact_info):
        """Create site in PayBC."""
        current_app.logger.debug('<Creating site ')
        if not contact_info:
            contact_info = {}
        site_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/' \
            .format(account.get('party_number', None), account.get('account_number', None))
        site: Dict[str, Any] = {
            'party_number': account.get('party_number', None),
            'account_number': account.get('account_number', None),
            'site_name': party.get('customer_name') + ' Site',
            'city': get_non_null_value(contact_info.get('city'), DEFAULT_CITY),
            'address_line_1': get_non_null_value(contact_info.get('addressLine1'), DEFAULT_ADDRESS_LINE_1),
            'postal_code': get_non_null_value(contact_info.get('postalCode'), DEFAULT_POSTAL_CODE).replace(' ', ''),
            'province': get_non_null_value(contact_info.get('province'), DEFAULT_JURISDICTION),
            'country': get_non_null_value(contact_info.get('country'), DEFAULT_COUNTRY),
            'customer_site_id': '1'
        }

        try:
            site_response = OAuthService.post(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                              site).json()
        except HTTPError as e:
            # If the site creation fails with 400, query and return site
            if e.response.status_code == 400:
                site_response = \
                    OAuthService.get(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON).json().get(
                        'items')[0]
            else:
                raise e
        current_app.logger.debug('>Creating site ')
        return site_response

    @staticmethod
    def get_token():
        """Generate oauth token from payBC which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('CFS_BASE_URL') + '/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('CFS_CLIENT_ID') + ':' + current_app.config.get('CFS_CLIENT_SECRET'),
                  'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = OAuthService.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC,
                                           ContentType.FORM_URL_ENCODED, data)
        current_app.logger.debug('>Getting token')
        return token_response


def get_non_null_value(value: str, default_value: str):
    """Return non null value for the value by replacing default value."""
    return default_value if (value is None or value.strip() == '') else value
