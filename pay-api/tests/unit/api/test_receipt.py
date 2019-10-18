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

import pytest
from tests.utilities.base_test import get_claims, get_payment_request, token_header


@pytest.fixture
def run_around_tests(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 201


def test_receipt_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

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

    filing_data = {
        'corpName': 'CP0001234',
        'filingDateTime': 'June 27, 2019',
        'fileName': 'director-change'
    }
    rv = client.post(f'/api/v1/payment-requests/{pay_id}/receipts', data=json.dumps(filing_data), headers=headers)
    assert rv.status_code == 201


def test_receipt_creation_with_invoice(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')
    inovice_id = rv.json.get('invoices')[0].get('id')
    payment_id = rv.json.get('id')
    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}?receipt_number={receipt_number}',
                 data=None, headers=headers)
    filing_data = {
        'corpName': 'CP0001234',
        'filingDateTime': 'June 27, 2019',
        'fileName': 'director-change'
    }
    rv = client.post(f'/api/v1/payment-requests/{pay_id}/invoices/{inovice_id}/receipts', data=json.dumps(filing_data),
                     headers=headers)
    assert rv.status_code == 201


def test_receipt_creation_with_invalid_request(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')
    inovice_id = rv.json.get('invoices')[0].get('id')
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    txn_id = rv.json.get('id')
    client.patch(f'/api/v1/payment-requests/{payment_id}/transactions/{txn_id}?receipt_number={receipt_number}',
                 data=None, headers=headers)
    filing_data = {
        'corpName': 'CP0001234'
    }
    rv = client.post(f'/api/v1/payment-requests/{pay_id}/invoices/{inovice_id}/receipts', data=json.dumps(filing_data),
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY999'


def test_receipt_creation_with_invalid_identifiers(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    payment_id = 1111
    inovice_id = 2222
    filing_data = {
        'corpName': 'CP0001234',
        'filingDateTime': 'June 27, 2019',
        'fileName': 'director-change'
    }
    rv = client.post(f'/api/v1/payment-requests/{payment_id}/invoices/{inovice_id}/receipts',
                     data=json.dumps(filing_data),
                     headers=headers)
    assert rv.status_code == 400
