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
"""Jobs uses service accounts to retrieve the token."""
import base64

from flask import current_app
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType


def get_token():
    """Get service account token."""
    issuer_url = current_app.config.get('JWT_OIDC_ISSUER')

    token_url = issuer_url + '/protocol/openid-connect/token'
    # https://sso-dev.pathfinder.gov.bc.ca/auth/realms/fcf0kpqr/protocol/openid-connect/token
    basic_auth_encoded = base64.b64encode(
        bytes(current_app.config.get('KEYCLOAK_SERVICE_ACCOUNT_ID') + ':' + current_app.config.get(
            'KEYCLOAK_SERVICE_ACCOUNT_SECRET'), 'utf-8')).decode('utf-8')
    data = 'grant_type=client_credentials'
    token_response = OAuthService.post(token_url, basic_auth_encoded,
                                       AuthHeaderType.BASIC, ContentType.FORM_URL_ENCODED, data)
    token = token_response.json().get('access_token')
    return token
