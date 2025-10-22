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

"""Tests to assure the bcol accounts end-point.

Test-Suite to ensure that the /accounts/<id>/users/<user_id> endpoint is working as expected.
"""

import json

from bcol_api.utils.errors import Error
from tests.utilities.base_test import get_claims, get_token_header


def test_post_accounts(client, jwt, app, ldap_mock, query_profile_mock):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/profiles",
        data=json.dumps({"userId": "TEST", "password": "TEST"}),
        headers=headers,
    )
    assert rv.status_code == 200


def test_post_accounts_invalid_request(client, jwt, app, ldap_mock, query_profile_mock):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/profiles",
        data=json.dumps({"user": "TEST", "password": "TEST"}),
        headers=headers,
    )
    assert rv.status_code == 400


def test_post_accounts_auth_error(client, jwt, app, ldap_mock_error, query_profile_mock):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/profiles",
        data=json.dumps({"userId": "TEST", "password": "TEST"}),
        headers=headers,
    )
    assert rv.status_code == 400


def test_post_accounts_query_error(client, jwt, app, ldap_mock, query_profile_mock_error):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/profiles",
        data=json.dumps({"userId": "TEST", "password": "TEST"}),
        headers=headers,
    )
    assert rv.status_code == 400


def test_post_accounts_not_prime_error(client, jwt, app, ldap_mock, query_profile_contact_mock):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/profiles",
        data=json.dumps({"userId": "TEST", "password": "TEST"}),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == Error.NOT_A_PRIME_USER.name


def test_get_profile(client, jwt, app, query_profile_mock):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role="system"), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.get("/api/v1/profiles/PB25020", headers=headers)
    assert rv.status_code == 200
