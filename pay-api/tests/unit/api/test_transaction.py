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

"""Tests to assure the transactions end-point.

Test-Suite to ensure that the /transactions endpoint is working as expected.
"""

import json
import uuid
from unittest.mock import patch

from requests.exceptions import ConnectionError
from tests import skip_in_pod
from tests.utilities.base_test import get_claims, get_payment_request, token_header

from pay_api.schemas import utils as schema_utils


def test_transaction_post(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('paymentId') == payment_id
    assert schema_utils.validate(rv.json, 'transaction')[0]


def test_transaction_post_no_redirect_uri(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps({}),
                     headers=headers)
    assert rv.status_code == 400


def test_transactions_post_invalid_payment(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payment_id = 9999
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps({}),
                     headers=headers)
    assert rv.status_code == 400


def test_transaction_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.get(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('paymentId') == payment_id
    assert rv.json.get('id') == txn_id
    assert schema_utils.validate(rv.json, 'transaction')[0]


def test_transaction_get_invalid_payment_and_transaction(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    invalid_payment_id = 999
    rv = client.get(f'/api/v1/payment-requests/{invalid_payment_id}/transactions/{txn_id}', headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY008'
    invalid_txn_id = uuid.uuid4()
    rv = client.get(f'/api/v1/payment-requests/{payment_id}/transactions/{invalid_txn_id}', headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY008'


def test_transaction_put(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}?receipt_number={receipt_number}',
                      data=None, headers=headers)
    assert rv.status_code == 200


def test_transaction_put_with_no_receipt(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}', data=None,
                      headers=headers)
    assert rv.status_code == 200


@skip_in_pod
def test_transaction_put_completed_payment(session, client, jwt, app, stan_server):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)

    txn_id = rv.json.get('id')
    rv = client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}', data=None,
                      headers=headers)

    rv = client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}', data=None,
                      headers=headers)

    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY006'


def test_transactions_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)

    transactions_link = rv.json.get('_links').get('transactions')
    rv = client.get(f'{transactions_link}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('items') is not None
    assert len(rv.json.get('items')) == 0

    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'{transactions_link}', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.get(f'{transactions_link}/{txn_id}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('id') == txn_id

    rv = client.get(f'{transactions_link}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('items') is not None
    assert len(rv.json.get('items')) == 1

    assert schema_utils.validate(rv.json, 'transactions')[0]


@skip_in_pod
def test_transaction_patch_completed_payment_and_transaction_status(session, client, jwt, app, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)

    txn_id = rv.json.get('id')
    rv = client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}', data=None,
                      headers=headers)

    assert rv.status_code == 200
    assert rv.json.get('statusCode') == 'COMPLETED'


@skip_in_pod
def test_transaction_patch_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        rv = client.patch(
            f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}?receipt_number={receipt_number}',
            data=None,
            headers=headers)
        assert rv.status_code == 200
        assert rv.json.get('paySystemReasonCode') == 'SERVICE_UNAVAILABLE'
