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

"""Tests to assure the bcol payments end-point.

Test-Suite to ensure that the /payments endpoint is working as expected.
"""

import json

from tests.utilities.base_test import get_claims, get_token_header


def test_post_payments(client, jwt, app, payment_mock):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/payments",
        data=json.dumps(
            {
                "feeCode": "BSH105",
                "userId": "PB25020",
                "invoiceNumber": "TEST12345678901",
                "folioNumber": "TEST1234567890",
                "formNumber": "",
                "quantity": "",
                "rate": "",
                "amount": "",
                "remarks": "TEST",
                "reduntantFlag": " ",
                "serviceFees": "1.50",
            }
        ),
        headers=headers,
    )
    assert rv.status_code == 200


def test_post_payments_invalid_request(client, jwt, app, payment_mock):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/payments",
        data=json.dumps({"feeCode": "BSH105", "userId": "PB25020"}),
        headers=headers,
    )
    assert rv.status_code == 400


def test_post_payments_error(client, jwt, app, payment_mock_error):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), get_token_header())
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    rv = client.post(
        "/api/v1/payments",
        data=json.dumps(
            {
                "feeCode": "BSH105",
                "userId": "PB25020",
                "invoiceNumber": "TEST12345678901",
                "folioNumber": "TEST1234567890",
                "formNumber": "",
                "quantity": "",
                "rate": "",
                "amount": "",
                "remarks": "TEST",
                "reduntantFlag": " ",
                "serviceFees": "1.50",
            }
        ),
        headers=headers,
    )
    assert rv.status_code == 400
