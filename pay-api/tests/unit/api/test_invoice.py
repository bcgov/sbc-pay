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

"""Tests to assure the invoice end-point.

Test-Suite to ensure that the /invoices endpoint is working as expected.
"""
import json
from unittest.mock import Mock, patch


INVOICE_REQUEST_CC = {
    'entity_name': 'TEST',
    'entity_legal_name': 'TEST',
    'site_name': 'TEST',
    'contact_first_name': 'TEST',
    'contact_last_name': 'TEST',
    'address_line_1': 'TEST',
    'city': 'TEST',
    'province': 'BC',
    'postal_code': 'A1A1A1',
    'batch_source': 'TEST',
    'customer_transaction_type': 'TEST',
    'total': '1000',
    'method_of_payment': 'CC',
    'lineItems': [
        {
            'line_number': '1',
            'line_type': 'LINE',
            'description': 'TEST',
            'unit_price': '1000',
            'quantity': '1'
        }
    ]
}


INVOICE_REQUEST_NON_CC = {
    'entity_name': 'TEST',
    'entity_legal_name': 'TEST',
    'site_name': 'TEST',
    'contact_first_name': 'TEST',
    'contact_last_name': 'TEST',
    'address_line_1': 'TEST',
    'city': 'TEST',
    'province': 'BC',
    'postal_code': 'A1A1A1',
    'batch_source': 'TEST',
    'customer_transaction_type': 'TEST',
    'total': '1000',
    'method_of_payment': 'BCOL',
    'lineItems': [
        {
            'line_number': '1',
            'line_type': 'LINE',
            'description': 'TEST',
            'unit_price': '1000',
            'quantity': '1'
        }
    ]
}


def test_paybc_invoice_for_credit_card(client, jwt, app):
    """Assert that the endpoint returns 201."""
    headers = {'Content-Type': 'application/json'}
    mock_responses = patch('pay_api.services.oauth_service.requests.post')
    mock_get = mock_responses.start()
    mock_get.return_value = Mock(status_code=201)
    mock_get.return_value.json.return_value = {'key': 'value'}

    rv = client.post('/api/v1/invoices', data=json.dumps(INVOICE_REQUEST_CC), headers=headers)
    mock_responses.stop()
    assert rv.status_code == 201


def test_paybc_invoice_for_non_credit_card(client, jwt, app):
    """Assert that the endpoint returns 201."""
    headers = {'Content-Type': 'application/json'}
    mock_responses = patch('pay_api.services.oauth_service.requests.post')
    mock_get = mock_responses.start()
    mock_get.return_value = Mock(status_code=201)
    mock_get.return_value.json.return_value = {'key': 'value'}

    rv = client.post('/api/v1/invoices', data=json.dumps(INVOICE_REQUEST_NON_CC), headers=headers)
    mock_responses.stop()

    assert rv.status_code == 201
