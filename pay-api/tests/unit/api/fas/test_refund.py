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

"""Tests to assure the routing-slips end-point.

Test-Suite to ensure that the /routing-slips endpoint is working as expected.
"""

import json

from faker import Faker

from pay_api.schemas import utils as schema_utils
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import PaymentMethod, Role, RoutingSlipStatus
from tests.utilities.base_test import get_claims, get_routing_slip_request, token_header

fake = Faker()


def test_refund_routing_slips(session, client, jwt):
    """Assert refund works for routing slips."""
    payload = get_routing_slip_request()
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value, Role.FAS_REFUND.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rv.json.get('number')), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    refund_details = {
        'mailingAddress': {
            'city': 'Gatineau',
            'country': 'CA',
            'region': 'QC',
            'postalCode': 'J8L 2K3',
            'street': 'E-412 Rue Charles',
            'streetAdditional': ''
        },
        'name': 'Staff user'
    }
    rs_number = rv.json.get('number')
    rv = client.post('/api/v1/fas/routing-slips/{}/refunds'.format(rs_number),
                     data=json.dumps({'status': RoutingSlipStatus.REFUND_REQUESTED.value, 'details': refund_details}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['ROUTINGSLIP.REFUND_REQUESTED']

    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rs_number), headers=headers)
    assert rv.json.get('status') == RoutingSlipStatus.REFUND_REQUESTED.value
    assert RoutingSlipStatus.REFUND_AUTHORIZED.value not in rv.json.get('allowedStatuses')
    refund = rv.json.get('refunds')[0]
    assert refund_details is not None
    assert refund_details.get('name') in refund.get('details').get('name')
    assert refund_details.get('mailingAddress') == refund.get('details').get('mailingAddress')

    rv = client.post('/api/v1/fas/routing-slips/{}/refunds'.format(rs_number),
                     data=json.dumps({'status': RoutingSlipStatus.REFUND_AUTHORIZED.value, 'details': refund_details}),
                     headers=headers)
    assert rv.status_code == 400

    token = jwt.create_jwt(
        get_claims(roles=[Role.FAS_SEARCH.value, Role.FAS_VIEW.value, Role.FAS_REFUND_APPROVER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/fas/routing-slips/{}/refunds'.format(rs_number),
                     data=json.dumps({'status': RoutingSlipStatus.REFUND_AUTHORIZED.value, 'details': refund_details}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['ROUTINGSLIP.REFUND_AUTHORIZED']

    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rs_number), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    assert rv.json.get('status') == RoutingSlipStatus.REFUND_AUTHORIZED.value


def test_refund_routing_slips_reject(session, client, jwt):
    """Assert refund works for routing slips."""
    payload = get_routing_slip_request()
    token = jwt.create_jwt(
        get_claims(
            roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value, Role.FAS_REFUND.value, Role.FAS_REFUND_APPROVER.value]),
        token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)

    rs_number = rv.json.get('number')
    rv = client.post('/api/v1/fas/routing-slips/{}/refunds'.format(rs_number),
                     data=json.dumps({'status': RoutingSlipStatus.REFUND_REQUESTED.value, }),
                     headers=headers)
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['ROUTINGSLIP.REFUND_REQUESTED']

    rv = client.post('/api/v1/fas/routing-slips/{}/refunds'.format(rs_number),
                     data=json.dumps({'status': RoutingSlipStatus.REFUND_REJECTED.value}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['ROUTINGSLIP.ACTIVE']

    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rs_number), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    assert rv.json.get('status') == RoutingSlipStatus.ACTIVE.value


def test_refund_routing_slips_zero_dollar_error(session, client, jwt):
    """Assert zero dollar refund fails."""
    payload = get_routing_slip_request(cheque_receipt_numbers=[('1234567890', PaymentMethod.CHEQUE.value, 0.00)])
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value, Role.FAS_REFUND.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rv.json.get('number')), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    refund_details = {
        'mailingAddress': {
            'city': 'Gatineau',
            'country': 'CA',
            'region': 'QC',
            'postalCode': 'J8L 2K3',
            'street': 'E-412 Rue Charles',
            'streetAdditional': ''
        },
        'name': 'Staff user'
    }
    rs_number = rv.json.get('number')
    rv = client.post('/api/v1/fas/routing-slips/{}/refunds'.format(rs_number),
                     data=json.dumps({'status': RoutingSlipStatus.REFUND_REQUESTED.value, 'details': refund_details}),
                     headers=headers)
    assert rv.status_code == 400
