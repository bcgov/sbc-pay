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

"""Tests to assure the routing-slips end-point.

Test-Suite to ensure that the /routing-slips endpoint is working as expected.
"""

import json

import pytest

from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import PatchActions, PaymentMethod, Role, RoutingSlipStatus
from tests.utilities.base_test import get_claims, get_routing_slip_request, token_header


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(),
    get_routing_slip_request(
        cheque_receipt_numbers=[('0001', PaymentMethod.CHEQUE.value, 100),
                                ('0002', PaymentMethod.CHEQUE.value, 100),
                                ('0003', PaymentMethod.CHEQUE.value, 100)
                                ]),
    get_routing_slip_request(cheque_receipt_numbers=[('0001', PaymentMethod.CASH.value, 2000)])
])
def test_create_routing_slips(session, client, jwt, app, payload):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_EDITOR.value, Role.FAS_USER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rv.json.get('number')), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(),
])
def test_create_routing_slips_unauthorized(session, client, jwt, app, payload):
    """Assert that the endpoint returns 401 for users with no fas_editor role."""
    token = jwt.create_jwt(get_claims(roles=[Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 401


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(),
])
def test_routing_slips_for_errors(session, client, jwt, app, payload):
    """Assert that the endpoint returns 401 for users with no fas_editor role."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_EDITOR.value, Role.FAS_USER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    # Create a duplicate and assert error.
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400
    # Try a routing slip with payment methods mix and match with a new routing slip number
    payload = get_routing_slip_request(number='TEST',
                                       cheque_receipt_numbers=[('0001', PaymentMethod.CASH.value, 100),
                                                               ('0002', PaymentMethod.CHEQUE.value, 100)])
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400

    # Get a routing slip which doesn't exist and assert 404
    rv = client.get('/api/v1/fas/routing-slips/5678987655678', headers=headers)
    assert rv.status_code == 404


def test_update_routing_slip_status(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_EDITOR.value, Role.FAS_USER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    rs_number = rv.json.get('number')

    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.COMPLETE.value}), headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('status') == RoutingSlipStatus.COMPLETE.value

    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.BOUNCED.value}), headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('status') == RoutingSlipStatus.BOUNCED.value

    # assert invalid action.
    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action=TEST',
                      data=json.dumps({'status': RoutingSlipStatus.BOUNCED.value}), headers=headers)
    assert rv.status_code == 400

    # Assert invalid number
    rv = client.patch(f'/api/v1/fas/routing-slips/TEST?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.BOUNCED.value}), headers=headers)
    assert rv.status_code == 400
