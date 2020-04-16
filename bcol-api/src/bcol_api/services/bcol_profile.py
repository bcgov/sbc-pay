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

from typing import Dict

import ldap
import zeep
from flask import current_app

from bcol_api.exceptions import BusinessException
from bcol_api.services.bcol_soap import BcolSoap
from bcol_api.utils.constants import account_type_mapping, auth_code_mapping, tax_status_mapping
from bcol_api.utils.errors import Error


class BcolProfile:  # pylint:disable=too-few-public-methods
    """Service to manage BCOL integration."""

    def query_profile(self, bcol_user_id: str, password: str):
        """Query for profile and return the results."""
        current_app.logger.debug('<query_profile')
        # Validate the user first
        self.__authenticate_user(bcol_user_id, password)

        # Call the query profile service to fetch profile
        data = {
            'Version': current_app.config.get('BCOL_DEBIT_ACCOUNT_VERSION'),
            'Userid': bcol_user_id,  # 'pc25020',
            'linkcode': current_app.config.get('BCOL_LINK_CODE'),
        }
        try:
            profile_resp = self.get_profile_response(data)
            current_app.logger.debug(profile_resp)
            auth_code = self.__get(profile_resp, 'AuthCode')
            if auth_code not in ('P', 'M'):
                raise BusinessException(Error.NOT_A_PRIME_USER)

            response = {
                'userId': self.__get(profile_resp, 'Userid'),
                'accountNumber': self.__get(profile_resp, 'AccountNumber'),
                'authCode': auth_code,
                'authCodeDesc': auth_code_mapping()[
                    self.__get(profile_resp, 'AuthCode')
                ],
                'accountType': self.__get(profile_resp, 'AccountType'),
                'accountTypeDesc': account_type_mapping()[
                    self.__get(profile_resp, 'AccountType')
                ],
                'gstStatus': self.__get(profile_resp, 'GSTStatus'),
                'gstStatusDesc': tax_status_mapping()[
                    self.__get(profile_resp, 'GSTStatus')
                ],
                'pstStatus': self.__get(profile_resp, 'PSTStatus'),
                'pstStatusDesc': tax_status_mapping()[
                    self.__get(profile_resp, 'PSTStatus')
                ],
                'userName': self.__get(profile_resp, 'UserName'),
                'orgName': self.__get(profile_resp, 'org-name'),
                'orgType': self.__get(profile_resp, 'org-type'),
                'phone': self.__get(profile_resp, 'UserPhone'),
                'fax': self.__get(profile_resp, 'UserFax'),
            }
            address = profile_resp['Address']
            if address:
                response['address'] = {
                    'line1': self.__get(address, 'AddressA'),
                    'line2': self.__get(address, 'AddressB'),
                    'city': self.__get(address, 'City'),
                    'province': self.__get(address, 'Prov'),
                    'country': self.__get(address, 'Country'),
                    'postalCode': self.__get(address, 'PostalCode'),
                }
            query_profile_flags = profile_resp['queryProfileFlag']
            if query_profile_flags:
                flags: list = []
                for flag in query_profile_flags:
                    flags.append(flag['name'])
                response['profile_flags'] = flags
        except BusinessException as e:
            raise e
        except Exception as e:
            current_app.logger.error(e)
            raise BusinessException(Error.SYSTEM_ERROR)

        current_app.logger.debug('>query_profile')
        return response

    def __authenticate_user(self, user_id: str, password: str) -> bool:  # pylint: disable=no-self-use
        """Validate the user by ldap lookup."""
        current_app.logger.debug('<<< _validate_user')
        ldap_conn = None
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # pylint: disable=no-member
            ldap_conn = ldap.initialize(
                current_app.config.get('BCOL_LDAP_SERVER'), trace_level=2
            )
            ldap_conn.set_option(ldap.OPT_REFERRALS, 0)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_X_TLS, ldap.OPT_X_TLS_DEMAND)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_X_TLS_DEMAND, True)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_DEBUG_LEVEL, 255)  # pylint: disable=no-member

            username = current_app.config.get('BCOL_LDAP_USER_DN_PATTERN').format(
                user_id
            )
            ldap_conn.simple_bind_s(username, password)
        except Exception as error:
            current_app.logger.warn(error)
            raise BusinessException(Error.INVALID_CREDENTIALS)
        finally:
            if ldap_conn:
                ldap_conn.unbind_s()

        current_app.logger.debug('>>> _validate_user')

    def __get(self, value: object, key: object) -> str:  # pylint: disable=no-self-use
        """Get the value from dict and strip."""
        if value and value[key]:
            return value[key].strip()
        return None

    def get_profile_response(self, data: Dict):  # pragma: no cover # pylint: disable=no-self-use
        """Get Query Profile Response."""
        client = BcolSoap().get_profile_client()
        return zeep.helpers.serialize_object(client.service.queryProfile(req=data))
