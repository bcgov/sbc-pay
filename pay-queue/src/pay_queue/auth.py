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

import requests
from flask import current_app
from requests.auth import HTTPBasicAuth


def get_token():
    """Get service account token."""
    issuer_url = current_app.config.get('JWT_OIDC_ISSUER')

    token_url = issuer_url + '/protocol/openid-connect/token'

    auth = HTTPBasicAuth(current_app.config.get('KEYCLOAK_SERVICE_ACCOUNT_ID'),
                         current_app.config.get('KEYCLOAK_SERVICE_ACCOUNT_SECRET'))
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    body = 'grant_type=client_credentials'

    token_request = requests.post(token_url, headers=headers, data=body, auth=auth, timeout=500)
    bearer_token = token_request.json()['access_token']
    return bearer_token
