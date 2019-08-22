# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A helper test.

Test-Suite to ensure that the /payments endpoint is working as expected.
"""

from pay_api.utils.enums import Role


token_header = {
    'alg': 'RS256',
    'typ': 'JWT',
    'kid': 'sbc-auth-cron-job'
}


def get_claims(app_request=None, role: str = Role.BASIC.value):
    """Return the claim with the role param."""
    claim = {
        'jti': 'a50fafa4-c4d6-4a9b-9e51-1e5e0d102878',
        'exp': 31531718745,
        'iat': 1531718745,
        'iss': app_request.config[
            'JWT_OIDC_ISSUER'] if app_request else 'https://sso-dev.pathfinder.gov.bc.ca/auth/realms/fcf0kpqr',
        'aud': 'sbc-auth-web',
        'sub': '15099883-3c3f-4b4c-a124-a1824d6cba84',
        'typ': 'Bearer',
        'realm_access':
            {
                'roles':
                    [
                        '{}'.format(role)
                    ]
            },
        'preferred_username': 'test'
    }
    return claim


def get_payment_request():
    """Return a payment request object."""
    return {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': 'CP1234',
            'corpType': 'CP',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'OTADD',
                    'filingDescription': 'TEST'
                },
                {
                    'filingTypeCode': 'OTANN'
                }
            ]
        }
    }
