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

"""Tests to assure the receipt end-point.

Test-Suite to ensure that the /receipt endpoint is working as expected.
"""

import json

from tests.utilities.base_test import get_claims, get_payment_request, token_header


def test_create_refund(session, client, jwt, app, stan_server):
    """Assert that the endpoint returns 202."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    inv_id = rv.json.get('id')

    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    client.patch(f'/api/v1/payment-requests/{inv_id}/transactions/{txn_id}',
                 data=json.dumps({'receipt_number': receipt_number}), headers=headers)

    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 202


def test_create_duplicate_refund_fails(session, client, jwt, app, stan_server):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    inv_id = rv.json.get('id')

    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    client.patch(f'/api/v1/payment-requests/{inv_id}/transactions/{txn_id}',
                 data=json.dumps({'receipt_number': receipt_number}), headers=headers)

    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test 2'}),
                     headers=headers)
    assert rv.status_code == 400
