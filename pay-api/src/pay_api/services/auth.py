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
from flask_jwt_oidc import JwtManager

from pay_api.services.oauth_service import OAuthService as RestService
from pay_api.utils.enums import AuthHeaderType, ContentType


def check_auth(business_identifier: str, jwt: JwtManager, **kwargs):
    """Authorize the user for the business entity."""
    bearer_token = jwt.get_token_auth_header() if jwt else None
    auth_url = current_app.config.get('AUTH_API_ENDPOINT') + f'entities/{business_identifier}/authorizations'
    auth_response = RestService.get(auth_url, bearer_token, AuthHeaderType.BEARER, ContentType.JSON)

    is_authorized: bool = False
    if auth_response:
        roles: list = auth_response.json().get('roles', [])
        if kwargs.get('one_of_roles', None):
            is_authorized = len(list(set(kwargs.get('one_of_roles')) & set(roles))) > 0
        if kwargs.get('contains_role', None):
            is_authorized = kwargs.get('contains_role') in roles

    if not is_authorized:
        abort(403)
