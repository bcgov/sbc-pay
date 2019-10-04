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

"""Tests to assure the invoices end-point.

Test-Suite to ensure that the /invoices endpoint is working as expected.
"""

import json

from pay_api.schemas import utils as schema_utils
from tests.utilities.base_test import get_claims, get_payment_request, token_header


def test_invoices_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 201
    invoices_link = rv.json.get('_links').get('invoices')
    rv = client.get(f'{invoices_link}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('items') is not None
    assert len(rv.json.get('items')) == 1
    assert schema_utils.validate(rv.json, 'invoices')[0]


def test_invoice_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 201
    invoices_link = rv.json.get('_links').get('invoices')
    rv = client.get(f'{invoices_link}', headers=headers)
    invoice_link = rv.json.get('items')[0].get('_links').get('self')
    rv = client.get(f'{invoice_link}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_invoice_get_invalid(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 201
    invoices_link = rv.json.get('_links').get('invoices')
    rv = client.get(f'{invoices_link}', headers=headers)
    invoice_link = rv.json.get('items')[0].get('_links').get('self')
    rv = client.get(f'{invoice_link}11', headers=headers)
    assert rv.status_code == 400
