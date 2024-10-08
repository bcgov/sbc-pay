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

"""Tests to assure the distributions end-point.

Test-Suite to ensure that the /fees endpoint is working as expected.
"""

from flask import json

from pay_api.utils.enums import Role
from tests.utilities.base_test import (
    get_claims,
    get_distribution_code_payload,
    get_distribution_schedules_payload,
    token_header,
)


def test_fee_schedules(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.STAFF.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get("/api/v1/fees/schedules", headers=headers)
    assert rv.status_code == 200


def test_fee_schedules_for_corp_and_filing_type(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.STAFF.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get("/api/v1/fees/schedules?corp_type=CP&filing_type=OTANN", headers=headers)
    assert rv.status_code == 200
    assert len(rv.json.get("items")) == 1


def test_create_distribution_with_invalid_data(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post("/api/v1/fees/distributions", data=json.dumps({}), headers=headers)
    assert rv.status_code == 400


def test_create_distribution_with_valid_data(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )
    assert rv.status_code == 201

    rv = client.get("/api/v1/fees/distributions", headers=headers)

    assert rv.status_code == 200
    assert rv.json is not None


def test_create_distribution_with_unauthorized_token(session, client, jwt, app):
    """Assert that the endpoint returns 401."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.STAFF.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )
    assert rv.status_code == 401


def test_get_distribution(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )
    assert rv.status_code == 201
    distribution_id = rv.json.get("distributionCodeId")
    rv = client.get(f"/api/v1/fees/distributions/{distribution_id}", headers=headers)
    assert rv.json.get("client") == get_distribution_code_payload().get("client")


def test_put_distribution(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )
    assert rv.status_code == 201
    distribution_id = rv.json.get("distributionCodeId")
    rv = client.put(
        f"/api/v1/fees/distributions/{distribution_id}",
        data=json.dumps(get_distribution_code_payload(client="200")),
        headers=headers,
    )
    assert rv.json.get("client") == "200"


def test_create_distribution_schedules(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )
    assert rv.status_code == 201
    distribution_id = rv.json.get("distributionCodeId")
    rv = client.post(
        f"/api/v1/fees/distributions/{distribution_id}/schedules",
        data=json.dumps(get_distribution_schedules_payload()),
        headers=headers,
    )
    assert rv.status_code == 201


def test_get_distribution_schedules(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )
    assert rv.status_code == 201
    distribution_id = rv.json.get("distributionCodeId")
    rv = client.post(
        f"/api/v1/fees/distributions/{distribution_id}/schedules",
        data=json.dumps(get_distribution_schedules_payload()),
        headers=headers,
    )
    assert rv.status_code == 201

    rv = client.get(f"/api/v1/fees/distributions/{distribution_id}/schedules", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("items")[0].get("feeScheduleId") == get_distribution_schedules_payload()[0].get("feeScheduleId")


def test_put_distribution_updates_invoice_status(session, client, jwt, app):
    """Assert that updating an existing fee distribution will update the invoice status."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_GL_CODES.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fees/distributions",
        data=json.dumps(get_distribution_code_payload()),
        headers=headers,
    )

    distribution_id = rv.json.get("distributionCodeId")
    rv = client.put(
        f"/api/v1/fees/distributions/{distribution_id}",
        data=json.dumps(get_distribution_code_payload(client="200")),
        headers=headers,
    )
    assert rv.json.get("client") == "200"
