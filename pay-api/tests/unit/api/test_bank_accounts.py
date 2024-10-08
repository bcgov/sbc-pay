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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""

import json

from tests.utilities.base_test import get_claims, token_header


def test_bank_account_valid_bank(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    valid_bank_details = {
        "bankInstitutionNumber": "001",
        "bankTransitNumber": "0720",
        "bankAccountNumber": "1234567",
    }

    rv = client.post(
        "/api/v1/bank-accounts/verifications",
        data=json.dumps(valid_bank_details),
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("isValid") is True


def test_bank_account_invalid_bank_one_error(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    valid_bank_details = {
        "bankInstitutionNumber": "0002",
        "bankTransitNumber": "00720",
        "bankAccountNumber": "12345678",
    }

    rv = client.post(
        "/api/v1/bank-accounts/verifications",
        data=json.dumps(valid_bank_details),
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("isValid") is False
    assert rv.json.get("message")[0] == "Bank Number is Invalid."


def test_bank_account_invalid_bank_multiple_error(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    valid_bank_details = {
        "bankInstitutionNumber": "003",
        "bankTransitNumber": "0720",
        "bankAccountNumber": "123456789",
    }

    rv = client.post(
        "/api/v1/bank-accounts/verifications",
        data=json.dumps(valid_bank_details),
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("isValid") is False
    assert len(rv.json.get("message")) == 3
    assert "Account number has invalid characters." in rv.json.get("message")
    assert "Account number has non-numeric characters." in rv.json.get("message")
    assert "Account number length is not valid for this bank." in rv.json.get("message")
