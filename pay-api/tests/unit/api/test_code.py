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

"""Tests to assure the fees end-point.

Test-Suite to ensure that the /fees endpoint is working as expected.
"""

import pytest

from pay_api.utils.enums import Code


def test_codes_valid(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    rv = client.get("/api/v1/codes/errors", headers={})
    assert rv.status_code == 200
    assert len(rv.json.get("codes")) > 0


def test_codes_invalid(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    rv = client.get("/api/v1/codes/xxxx", headers={})
    assert rv.json.get("codes") is None


def test_find_code(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    rv = client.get("/api/v1/codes/errors", headers={})
    code = rv.json.get("codes")[0].get("type")
    rv = client.get(f"/api/v1/codes/errors/{code}", headers={})
    assert rv.json.get("type") == code


@pytest.mark.parametrize("code", list(map(Code, Code)))
def test_find_codes(session, client, jwt, app, code: Code):
    """Assert that the endpoint returns 200."""
    rv = client.get(f"/api/v1/codes/{code.value}", headers={})
    assert rv.status_code == 200


def test_get_valid_payment_methods(session, client, jwt, app):
    """Assert that the valid payment methods endpoint works."""
    rv = client.get("/api/v1/codes/valid_payment_methods", headers={})
    assert rv.status_code == 200
    assert isinstance(rv.json, dict)

    rv = client.get("/api/v1/codes/valid_payment_methods/VS", headers={})
    assert rv.status_code == 200
    assert isinstance(rv.json, dict)

    rv = client.get("/api/v1/codes/valid_payment_methods/INVALID", headers={})
    assert rv.status_code == 200
    assert rv.json == {"INVALID": []}
