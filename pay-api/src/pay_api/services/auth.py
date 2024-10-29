# Copyright © 2024 Province of British Columbia
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

"""This manages all of the authorization service."""
import base64
from typing import List

from flask import abort, current_app, g

from pay_api.services.code import Code as CodeService
from pay_api.services.flags import flags
from pay_api.services.oauth_service import OAuthService as RestService
from pay_api.utils.enums import AccountType, AuthHeaderType, Code, ContentType, PaymentMethod, Role
from pay_api.utils.user_context import UserContext, user_context

PREMIUM_ACCOUNT_TYPES = (
    AccountType.PREMIUM.value,
    AccountType.SBC_STAFF.value,
    AccountType.STAFF.value,
)


@user_context
def check_auth(
    business_identifier: str,
    account_id: str = None,
    corp_type_code: str = None,
    **kwargs,
):  # pylint: disable=unused-argument, too-many-branches, too-many-statements
    """Authorize the user for the business entity and return authorization response."""
    user: UserContext = kwargs["user"]
    is_authorized: bool = False
    auth_response = None
    product_code = CodeService.find_code_value_by_type_and_code(Code.CORP_TYPE.value, corp_type_code).get("product")
    account_id = account_id or user.account_id

    call_auth_svc: bool = True

    if user.is_system():
        is_authorized = bool(Role.EDITOR.value in user.roles)
        if product_code:
            is_authorized = is_authorized and product_code == user.product_code

        # Call auth only if it's business (entities), as affiliation is the auhtorization
        if user.product_code != "BUSINESS":
            call_auth_svc = False
            # Add account name as the service client name
            auth_response = {"account": {"id": user.account_id or user.user_name}}

    if call_auth_svc:
        bearer_token = user.bearer_token
        current_app.logger.info(
            f"Checking auth for Account : {account_id}, Business : {business_identifier}, "
            f"Is Staff : {user.is_staff()}"
        )
        roles: list = []
        auth_response = {}

        if account_id:
            auth_url = (
                current_app.config.get("AUTH_API_ENDPOINT") + f"orgs/{account_id}" f"/authorizations?expanded=true"
            )
            additional_headers = None
            if corp_type_code:
                additional_headers = {"Product-Code": product_code}
            auth_response = (
                RestService.get(
                    auth_url,
                    bearer_token,
                    AuthHeaderType.BEARER,
                    ContentType.JSON,
                    additional_headers=additional_headers,
                ).json()
                or {}
            )
            roles: list = auth_response.get("roles", [])
            g.account_id = account_id
        elif business_identifier:
            auth_url = (
                current_app.config.get("AUTH_API_ENDPOINT")
                + f"entities/{business_identifier}/authorizations?expanded=true"
            )
            auth_response = (
                RestService.get(auth_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON).json() or {}
            )

            roles: list = auth_response.get("roles", [])
            g.account_id = auth_response.get("account").get("id") if auth_response.get("account", None) else None
        elif user.is_staff():
            roles: list = user.roles
            auth_response = {}
        else:
            current_app.logger.info("No Auth Information Found")

        g.user_permission = auth_response.get("roles")
        if kwargs.get("one_of_roles", None):
            is_authorized = len(list(set(kwargs.get("one_of_roles")) & set(roles))) > 0
        if kwargs.get("contains_role", None):
            is_authorized = kwargs.get("contains_role") in roles
        if required_roles := kwargs.get("all_of_roles", None):
            is_authorized = len(set(required_roles) & set(roles)) == len(set(required_roles))
        # Check if premium flag is required
        if (
            flags.is_on("remove-premium-restrictions", default=False) is False
            and kwargs.get("is_premium", False)
            and auth_response["account"]["accountType"] not in PREMIUM_ACCOUNT_TYPES
        ):
            is_authorized = False
        # For staff users, if the account is coming as empty add stub data
        # (businesses which are not affiliated won't have account)
        if user.is_staff() and not auth_response.get("account", None):
            auth_response["account"] = {"id": f"PASSCODE_ACCOUNT_{business_identifier}"}

        if user.is_system() and bool(Role.EDITOR.value in user.roles):
            is_authorized = True

    if not is_authorized:
        abort(403)

    # IF auth response is empty (means a service account or a business with no account by staff)
    if not auth_response:
        if Role.SYSTEM.value in user.roles:  # Call auth only if it's business (entities)
            # Add account name as the service client name
            auth_response = {
                "account": {
                    "id": user.user_name,
                    "paymentInfo": {"methodOfPayment": PaymentMethod.DIRECT_PAY.value},
                }
            }
    return auth_response


@user_context
def get_account_admin_users(auth_account_id, **kwargs):
    """Retrieve account admin users."""
    # Only works for STAFF and ADMINS of the org.
    return RestService.get(
        current_app.config.get("AUTH_API_ENDPOINT") + f"orgs/{auth_account_id}/members?status=ACTIVE&roles=ADMIN",
        kwargs["user"].bearer_token,
        AuthHeaderType.BEARER,
        ContentType.JSON,
    ).json()


def get_emails_with_keycloak_role(role: str) -> List[str]:
    """Retrieve emails with the specified keycloak role."""
    users = get_users_with_keycloak_role(role)
    # Purpose of this is so our TEST users don't get hammered with emails, also our tester can easily switch this on.
    if flags.is_on("override-eft-refund-emails", default=False):
        return flags.value("override-eft-refund-emails").split(",")
    return [user["email"] for user in users]


def get_users_with_keycloak_role(role: str) -> dict:
    """Retrieve users with the specified keycloak role."""
    url = current_app.config.get("AUTH_API_ENDPOINT") + f"keycloak/users?role={role}"
    return RestService.get(url, get_service_account_token(), AuthHeaderType.BEARER, ContentType.JSON).json()


def get_service_account_token():
    """Get service account token."""
    issuer_url = current_app.config.get("JWT_OIDC_ISSUER")
    token_url = issuer_url + "/protocol/openid-connect/token"
    service_account_id = current_app.config.get("KEYCLOAK_SERVICE_ACCOUNT_ID")
    service_account_secret = current_app.config.get("KEYCLOAK_SERVICE_ACCOUNT_SECRET")
    auth_str = f"{service_account_id}:{service_account_secret}"
    basic_auth_encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    data = "grant_type=client_credentials"
    token_response = RestService.post(
        token_url,
        basic_auth_encoded,
        AuthHeaderType.BASIC,
        ContentType.FORM_URL_ENCODED,
        data,
    )
    bearer_token = token_response.json()["access_token"]
    return bearer_token
