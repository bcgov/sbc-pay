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

"""This manages all of the authorization service."""
from flask import abort, current_app, g

from pay_api.services.oauth_service import OAuthService as RestService
from pay_api.utils.enums import AccountType, AuthHeaderType, ContentType, PaymentMethod, Role
from pay_api.utils.user_context import UserContext, user_context


@user_context
def check_auth(business_identifier: str, account_id: str = None, corp_type_code: str = None,
               **kwargs):  # pylint: disable=unused-argument, too-many-branches
    """Authorize the user for the business entity and return authorization response."""
    user: UserContext = kwargs['user']
    is_authorized: bool = False
    auth_response = {}

    if not account_id:
        account_id = user.account_id

    call_auth_svc: bool = True

    if Role.SYSTEM.value in user.roles \
            and user.product_code != 'BUSINESS':  # Call auth only if it's business (entities)
        call_auth_svc = False
        is_authorized = bool(Role.EDITOR.value in user.roles)
        # Add account name as the service client name
        auth_response = {'account': {'id': user.user_name}}

    if call_auth_svc:
        bearer_token = user.bearer_token
        if account_id:
            auth_url = current_app.config.get('AUTH_API_ENDPOINT') + f'orgs/{account_id}' \
                                                                     f'/authorizations?expanded=true'
            additional_headers = None
            if corp_type_code:
                additional_headers = {'Product-Code': corp_type_code}
            auth_response = RestService.get(auth_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON,
                                            additional_headers=additional_headers).json()
            roles: list = auth_response.get('roles', [])
            g.account_id = account_id
        elif business_identifier:
            auth_url = current_app.config.get(
                'AUTH_API_ENDPOINT') + f'entities/{business_identifier}/authorizations?expanded=true'
            auth_response = RestService.get(auth_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON).json()

            roles: list = auth_response.get('roles', [])
            g.account_id = auth_response.get('account').get('id') if auth_response.get('account', None) else None
        elif Role.STAFF.value in user.roles:
            roles: list = user.roles

        g.user_permission = auth_response.get('roles')
        if kwargs.get('one_of_roles', None):
            is_authorized = list(set(kwargs.get('one_of_roles')) & set(roles)) != []
        if kwargs.get('contains_role', None):
            is_authorized = kwargs.get('contains_role') in roles
        # Check if premium flag is required
        if kwargs.get('is_premium', False) and auth_response['account']['accountType'] != AccountType.PREMIUM.value:
            is_authorized = False
        # For staff users, if the account is coming as empty add stub data
        # (businesses which are not affiliated won't have account)
        if Role.STAFF.value in user.roles and not auth_response.get('account', None):
            auth_response['account'] = {
                'id': f'PASSCODE_ACCOUNT_{business_identifier}'
            }

        if Role.SYSTEM.value in user.roles and bool(Role.EDITOR.value in user.roles):
            is_authorized = True

    if not is_authorized:
        abort(403)

    # IF auth response is empty (means a service account or a business with no account by staff)
    if not auth_response:
        if Role.SYSTEM.value in user.roles:  # Call auth only if it's business (entities)
            # Add account name as the service client name
            auth_response = {'account': {'id': user.user_name,
                                         'paymentInfo': {'methodOfPayment': PaymentMethod.DIRECT_PAY.value}}}
    return auth_response
