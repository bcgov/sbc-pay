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

"""Tests to assure the invoices end-point.

Test-Suite to ensure that the /invoices endpoint is working as expected.
"""

import json

from tests.utilities.base_test import get_claims, get_payment_request, token_header


def test_get_invoice(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)
    inv_id = rv.json.get('id')
    rv = client.get(f'/api/v1/payment-requests/{inv_id}/invoices', headers=headers)
    assert rv.json.get('items')[0].get('id') == inv_id
