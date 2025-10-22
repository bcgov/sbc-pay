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

import ldap
import pycountry
import zeep
from flask import current_app

from bcol_api.exceptions import BusinessException, PaymentException
from bcol_api.services.bcol_soap import BcolSoap
from bcol_api.utils.constants import account_type_mapping, auth_code_mapping, tax_status_mapping
from bcol_api.utils.errors import Error


class BcolProfile:  # pylint:disable=too-few-public-methods
    """Service to manage BCOL integration."""

    def query_profile(self, bcol_user_id: str, password: str):
        """Query for profile and return the results."""
        current_app.logger.debug("<query_profile")
        # Validate the user first
        self.__authenticate_user(bcol_user_id, password)

        response = self.get_profile(bcol_user_id)

        current_app.logger.debug(">query_profile")
        return response

    def get_profile(self, bcol_user_id):
        """Return bcol profile by user id."""
        # Call the query profile service to fetch profile
        data = {
            "Version": current_app.config.get("BCOL_DEBIT_ACCOUNT_VERSION"),
            "Userid": bcol_user_id,  # 'pc25020',
            "linkcode": current_app.config.get("BCOL_LINK_CODE"),
        }
        try:
            profile_resp = self.get_profile_response(data)
            current_app.logger.debug(profile_resp)
            auth_code = self.__get(profile_resp, "AuthCode")
            if auth_code != "P":
                raise BusinessException(Error.NOT_A_PRIME_USER)

            response = {
                "userId": self.__get(profile_resp, "Userid"),
                "accountNumber": self.__get(profile_resp, "AccountNumber"),
                "authCode": auth_code,
                "authCodeDesc": auth_code_mapping()[self.__get(profile_resp, "AuthCode")],
                "accountType": self.__get(profile_resp, "AccountType"),
                "accountTypeDesc": account_type_mapping()[self.__get(profile_resp, "AccountType")],
                "gstStatus": self.__get(profile_resp, "GSTStatus"),
                "gstStatusDesc": tax_status_mapping()[self.__get(profile_resp, "GSTStatus")],
                "pstStatus": self.__get(profile_resp, "PSTStatus"),
                "pstStatusDesc": tax_status_mapping()[self.__get(profile_resp, "PSTStatus")],
                "userName": self.__get(profile_resp, "UserName"),
                "orgName": self.__get(profile_resp, "org-name"),
                "orgType": self.__get(profile_resp, "org-type"),
                "phone": self.__get(profile_resp, "UserPhone"),
                "fax": self.__get(profile_resp, "UserFax"),
            }
            address = profile_resp["Address"]
            if address:
                country = self.standardize_country(self.__get(address, "Country"))

                response["address"] = {
                    "line1": self.__get(address, "AddressA"),
                    "line2": self.__get(address, "AddressB"),
                    "city": self.__get(address, "City"),
                    "province": self.__get(address, "Prov"),
                    "country": country,
                    "postalCode": self.__get(address, "PostalCode"),
                }
            query_profile_flags = profile_resp["queryProfileFlag"]
            if query_profile_flags:
                flags: list = []
                for flag in query_profile_flags:
                    value = dict(flag).get("_value_1")
                    if value and value.strip() == "Y":
                        flags.append(flag["name"])
                response["profile_flags"] = flags
        except zeep.exceptions.Fault as fault:
            current_app.logger.error(fault)
            parsed_fault_detail = BcolSoap().get_profile_client().wsdl.types.deserialize(fault.detail[0])
            current_app.logger.error(parsed_fault_detail)
            raise PaymentException(
                message=self.__get(parsed_fault_detail, "message"),
                code=self.__get(parsed_fault_detail, "returnCode"),
            ) from fault
        except BusinessException as e:
            raise e from e
        except Exception as e:  # NOQA
            current_app.logger.error(e)
            raise BusinessException(Error.SYSTEM_ERROR) from e
        return response

    def __authenticate_user(self, user_id: str, password: str) -> bool:
        """Validate the user by ldap lookup."""
        current_app.logger.debug("<<< _validate_user")
        ldap_conn = None
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # pylint: disable=no-member
            ldap_conn = ldap.initialize(current_app.config.get("BCOL_LDAP_SERVER"), trace_level=2)
            ldap_conn.set_option(ldap.OPT_REFERRALS, 0)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)  # pylint: disable=no-member
            # ldap_conn.set_option(ldap.OPT_X_TLS, ldap.OPT_X_TLS_DEMAND)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_X_TLS_DEMAND, True)  # pylint: disable=no-member
            ldap_conn.set_option(ldap.OPT_DEBUG_LEVEL, 255)  # pylint: disable=no-member

            username = current_app.config.get("BCOL_LDAP_USER_DN_PATTERN").format(user_id)
            ldap_conn.simple_bind_s(username, password)
        except Exception as error:  # NOQA
            current_app.logger.warning(error)
            raise BusinessException(Error.INVALID_CREDENTIALS) from error
        finally:
            if ldap_conn:
                ldap_conn.unbind_s()

        current_app.logger.debug(">>> _validate_user")

    def __get(self, value: object, key: object) -> str:
        """Get the value from dict and strip."""
        if value and value[key]:
            return value[key].strip() if isinstance(value[key], str) else value[key]
        return None

    def get_profile_response(self, data: dict):  # pragma: no cover
        """Get Query Profile Response."""
        client = BcolSoap().get_profile_client()
        return zeep.helpers.serialize_object(client.service.queryProfile(req=data))

    @staticmethod
    def standardize_country(country):
        """Standardize country to 2 letters country code, return original if no country code found."""
        if len(country) == 2:
            return country.upper()

        country_info = pycountry.countries.get(name=country)
        if country_info:
            return country_info.alpha_2

        return country
