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
from typing import Dict, Any, Tuple

from flask import current_app
from requests import HTTPError

from pay_api.services.oauth_service import OAuthService
from pay_api.utils.constants import (
    DEFAULT_ADDRESS_LINE_1, DEFAULT_CITY, DEFAULT_COUNTRY, DEFAULT_CURRENCY, DEFAULT_JURISDICTION, DEFAULT_POSTAL_CODE)
from pay_api.utils.enums import AuthHeaderType, ContentType


class CFSService(OAuthService):
    """Service to invoke CFS related operations."""

    @classmethod
    def create_cfs_account(cls, name: str, contact_info: Dict[str, Any],
                           payment_info: Dict[str, any] = None, receipt_method: str = None) -> Dict[str, str]:
        """Create a cfs account and return the details."""
        name = re.sub(r'[^a-zA-Z0-9]+', ' ', name)
        access_token = CFSService.get_token().json().get('access_token')
        party = CFSService._create_party(access_token, name)
        account = CFSService._create_paybc_account(access_token, party)
        site = CFSService._create_site(access_token, party, account, contact_info, receipt_method)
        account_details = {
            'party_number': party.get('party_number'),
            'account_number': account.get('account_number'),
            'site_number': site.get('site_number')
        }
        if payment_info:
            account_details.update(cls._save_bank_details(access_token, party.get('party_number'),
                                                          account.get('account_number'),
                                                          site.get('site_number'), payment_info))

        return account_details

    @staticmethod
    def validate_bank_account(bank_details: Tuple[Dict[str, Any]]):
        """Validate bank details by invoking CFS validation Service."""
        current_app.logger.debug('<Validating bank account details')
        validation_url = current_app.config.get('CFS_BASE_URL') + '/validatepayins'
        bank_details: Dict[str, str] = {
            'accountNumber': bank_details.get('accountNumber', None),
            'branchNumber': bank_details.get('branchNumber', None),
            'bankNumber': bank_details.get('bankNumber', None),
        }

        try:
            access_token = CFSService.get_token().json().get('access_token')
            bank_validation_response = OAuthService.post(validation_url, access_token, AuthHeaderType.BEARER,
                                                         ContentType.JSON,
                                                         bank_details).json()

            validation_response = {
                'bank_number': bank_validation_response.get('bank_number', None),
                'bank_name': bank_validation_response.get('bank_number', None),
                'branch_number': bank_validation_response.get('branch_number', None),
                'transit_address': bank_validation_response.get('transit_address', None),
                'account_number': bank_validation_response.get('account_number', None),
                'is_valid': bank_validation_response.get('CAS-Returned-Messages', None) == 'VALID',
                'message': CFSService._transform_error_message(bank_validation_response.get('CAS-Returned-Messages'))
            }

        except HTTPError as e:
            current_app.logger.error(e)
            validation_response = {
                'is_valid': False,
                'message': 'Bank validation service cant be reached'
            }
        return validation_response

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
    def _transform_error_message(param: str):
        """Strip out unwanted characters from the CFS returned error message."""
        # [-+]?[0-9]+ -  matches the CFS format of 0001 -  etc.
        list_messages = re.split('[-+]?[0-9]+ - ', param)
        # strip out first empty
        stipped_message = list(filter(None, list_messages))
        return stipped_message

    @staticmethod
    def _create_paybc_account(access_token, party):
        """Create account record in PayBC."""
        current_app.logger.debug('<Creating account')
        account_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/'.format(
            party.get('party_number', None))
        account: Dict[str, Any] = {
            'account_description': current_app.config.get('CFS_ACCOUNT_DESCRIPTION')
        }

        account_response = OAuthService.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                             account)
        current_app.logger.debug('>Creating account')
        return account_response.json()

    @staticmethod
    def _create_site(access_token, party, account, contact_info, receipt_method):
        """Create site in PayBC."""
        current_app.logger.debug('<Creating site ')
        if not contact_info:
            contact_info = {}
        site_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/' \
            .format(account.get('party_number', None), account.get('account_number', None))
        site: Dict[str, Any] = {
            'site_name': party.get('customer_name'),  # TODO Check with CFS what is the best practice for this.
            'city': get_non_null_value(contact_info.get('city'), DEFAULT_CITY),
            'address_line_1': get_non_null_value(contact_info.get('addressLine1'), DEFAULT_ADDRESS_LINE_1),
            'postal_code': get_non_null_value(contact_info.get('postalCode'), DEFAULT_POSTAL_CODE).replace(' ', ''),
            'province': get_non_null_value(contact_info.get('province'), DEFAULT_JURISDICTION),
            'country': get_non_null_value(contact_info.get('country'), DEFAULT_COUNTRY),
            'customer_site_id': '1',
            'primary_bill_to': 'Y',
            'receipt_method': receipt_method
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

    @classmethod
    def _save_bank_details(cls, access_token, party_number, account_number,  # pylint: disable=too-many-arguments
                           site_number, payment_info):
        """Save bank details to the site."""
        current_app.logger.debug('<Creating payment details ')
        site_payment_url = current_app.config.get(
            'CFS_BASE_URL') + f'/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/payment/'

        payment_details: Dict[str, Any] = {
            'bank_number': str(payment_info.get('bankInstitutionNumber')),
            'branch_number': str(payment_info.get('bankTransitNumber')),
            'bank_account_number': str(payment_info.get('bankAccountNumber')),
            'country': DEFAULT_COUNTRY,
            'currency_code': DEFAULT_CURRENCY
        }
        site_payment_response = OAuthService.post(site_payment_url, access_token, AuthHeaderType.BEARER,
                                                  ContentType.JSON,
                                                  payment_details).json()

        payment_details = {
            'bank_account_number': payment_info.get('bankAccountNumber'),
            'bank_number': payment_info.get('bankInstitutionNumber'),
            'bank_branch_number': payment_info.get('bankTransitNumber'),
            'payment_instrument_number': site_payment_response.get('payment_instrument_number')
        }

        current_app.logger.debug('>Creating payment details')
        return payment_details

    @classmethod
    def update_bank_details(cls, party_number, account_number, site_number, payment_info):
        """Update bank details to the site."""
        current_app.logger.debug('<Update bank details ')
        access_token = CFSService.get_token().json().get('access_token')
        return cls._save_bank_details(access_token, party_number, account_number, site_number, payment_info)

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
