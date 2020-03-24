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
from flask import abort, current_app

from pay_api.services.oauth_service import OAuthService as RestService
from pay_api.utils.enums import AuthHeaderType, ContentType, Role
from pay_api.utils.user_context import UserContext, user_context


@user_context
def check_auth(business_identifier: str, account_id: str = None, corp_type_code: str = None,
               **kwargs):  # pylint: disable=unused-argument
    """Authorize the user for the business entity and return authorization response."""
    user: UserContext = kwargs['user']
    is_authorized: bool = False
    auth_response = None
    is_business_auth = True
    is_service_account = False
    account = None

    if not account_id:
        account_id = user.account_id
    if Role.SYSTEM.value in user.roles:
        is_authorized = bool(Role.EDITOR.value in user.roles)
        is_service_account = True
    else:
        bearer_token = user.bearer_token
        if business_identifier:
            auth_url = current_app.config.get(
                'AUTH_API_ENDPOINT') + f'entities/{business_identifier}/authorizations?expanded=true'
            auth_response = RestService.get(auth_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON).json()

            roles: list = auth_response.get('roles', [])
            if kwargs.get('one_of_roles', None):
                is_authorized = list(set(kwargs.get('one_of_roles')) & set(roles)) != []
            if kwargs.get('contains_role', None):
                is_authorized = kwargs.get('contains_role') in roles

        elif account_id:
            is_business_auth = False
            # TODO For now, just make a call to /orgs/<id> to see if the user has access to the account
            # When product level subscription is in place, use the below commented code.
            # auth_url = current_app.config.get(
            #     'AUTH_API_ENDPOINT') + f'accounts/{account_id}/products/{corp_type_code}/authorizations?expanded=true'
            # auth_response = RestService.get(auth_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON).json()
            # roles: list = auth_response.get('roles', [])
            # if roles:
            #     is_authorized = True

            # TODO Remove the below call and uncomment the above code once product subscription is in place.
            account_url = current_app.config.get(
                'AUTH_API_ENDPOINT') + f'orgs/{account_id}'
            account = RestService.get(account_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON,
                                      retry_on_failure=True).json()
            auth_response = {}
            is_authorized = True

    if not is_authorized:
        abort(403)
    # TODO Remove this code once the authorizations endpoint returns the account details
    if not is_service_account:
        if is_business_auth:
            account_url = current_app.config.get(
                'AUTH_API_ENDPOINT') + f'orgs?affiliation={business_identifier}'
            account_response = RestService.get(account_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON,
                                               retry_on_failure=True).json()
            if account_response and len(account_response.get('orgs')) == 1:
                account = account_response.get('orgs')[0]
            else:
                # If there is no auth account, then treat it as a passcode account
                account = {
                    'id': f'PASSCODE_ACCOUNT_{business_identifier}'
                }
        # else:
        #     account_url = current_app.config.get(
        #         'AUTH_API_ENDPOINT') + f'orgs/{account_id}'
        #     account_response = RestService.get(account_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON,
        #                                        retry_on_failure=True).json()
        auth_response['account'] = {'paymentPreference': {}}
        auth_response['account']['id'] = account.get('id', None)
        auth_response['account']['name'] = account.get('name', None)
        auth_response['account']['paymentPreference']['methodOfPayment'] = account.get('preferred_payment', None)
        auth_response['account']['paymentPreference']['bcOnlineUserId'] = account.get('bc_online_user_id', None)
    return auth_response
