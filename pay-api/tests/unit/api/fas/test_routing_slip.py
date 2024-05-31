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
from datetime import date, datetime, timedelta
from typing import Dict

import pytest
from flask import current_app
from faker import Faker

from pay_api.models import PaymentAccount, RoutingSlip
from pay_api.schemas import utils as schema_utils
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.services.fas.routing_slip_status_transition_service import RoutingSlipStatusTransitionService
from pay_api.utils.enums import PatchActions, PaymentMethod, Role, RoutingSlipCustomStatus, RoutingSlipStatus
from tests.utilities.base_test import factory_invoice, get_claims, get_routing_slip_request, token_header

fake = Faker()


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(number='206380792'),
    get_routing_slip_request(
        cheque_receipt_numbers=[('0001', PaymentMethod.CHEQUE.value, 100),
                                ('0002', PaymentMethod.CHEQUE.value, 100),
                                ('0003', PaymentMethod.CHEQUE.value, 100)
                                ]),
    get_routing_slip_request(cheque_receipt_numbers=[('0001', PaymentMethod.CASH.value, 2000)])
])
def test_create_routing_slips(session, client, jwt, payload):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rv.json.get('number')), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    allowed_statuses = rv.json.get('allowedStatuses')
    assert len(allowed_statuses) == len(RoutingSlipStatusTransitionService.STATUS_TRANSITIONS.get('ACTIVE'))


def test_create_routing_slips_search(session, client, jwt, app):
    """Assert that the search works."""
    claims = get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value])
    token = jwt.create_jwt(claims, token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request(number='206380800')
    initiator = claims.get('name')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    rs_number = rv.json.get('number')
    # do the searches

    # search with routing slip number works
    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'routingSlipNumber': rs_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('number') == rs_number

    # search with partial routing slip number works

    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'routingSlipNumber': rs_number[1:-1]}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('number') == rs_number

    # search with initiator

    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'routingSlipNumber': rs_number, 'initiator': initiator}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('number') == rs_number

    # search with dates

    valid_date_filter = {'startDate': (date.today() - timedelta(1)).strftime(DT_SHORT_FORMAT),
                         'endDate': (date.today() + timedelta(1)).strftime(DT_SHORT_FORMAT)}
    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'routingSlipNumber': rs_number, 'dateFilter': valid_date_filter}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('number') == rs_number

    invalid_date_filter = {'startDate': (date.today() + timedelta(100)).strftime(DT_SHORT_FORMAT),
                           'endDate': (date.today() + timedelta(1)).strftime(DT_SHORT_FORMAT)}
    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'routingSlipNumber': rs_number, 'dateFilter': invalid_date_filter}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 0

    # search using status
    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'status': 'ACTIVE'}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('number') == rs_number

    # search using invalid status
    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'status': 'COMPLETED'}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 0


def test_link_routing_slip_parent_is_a_child(session, client, jwt):
    """Assert linking to a child fails."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value, Role.FAS_SEARCH.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    child = get_routing_slip_request('206380842')
    parent1 = get_routing_slip_request('206380867')
    parent2 = get_routing_slip_request('206380891')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent1), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent2), headers=headers)

    # link parent 1 to parent 2

    data = {'childRoutingSlipNumber': f"{parent1.get('number')}", 'parentRoutingSlipNumber': f"{parent2.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('status') == 'LINKED'

    # now link child to parent

    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent1.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_PARENT_ALREADY_LINKED'
    assert rv.status_code == 400


def test_link_nsf(session, client, jwt):
    """Assert linking to a child fails."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value,
                                             Role.FAS_SEARCH.value, Role.FAS_EDIT.value]),
                           token_header)

    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    child = get_routing_slip_request('206380842')
    parent = get_routing_slip_request('206380867')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent), headers=headers)

    rv = client.patch(f"/api/v1/fas/routing-slips/{child.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.NSF.value}), headers=headers)
    assert rv.status_code == 200, 'status changed successfully.'

    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == 'RS_CANT_LINK_NSF'
    assert rv.json.get('title') == 'Routing Slip cannot be linked.'


def test_link_routing_slip_invalid_status(session, client, jwt, app):
    """Assert that the linking of routing slip works as expected."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value,
                                             Role.FAS_SEARCH.value, Role.FAS_REFUND.value,
                                             Role.FAS_EDIT.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    child = get_routing_slip_request('206380859')
    parent = get_routing_slip_request('206380909')
    child1 = get_routing_slip_request('206380883')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child1), headers=headers)

    rv = client.get(f"/api/v1/fas/routing-slips/{child.get('number')}/links", headers=headers)
    assert rv.json.get('parent') is None

    rv = client.patch(f"/api/v1/fas/routing-slips/{child.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.WRITE_OFF_REQUESTED.value}), headers=headers)
    assert rv.status_code == 200, 'status changed successfully.'

    # link them together ,success cases
    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == 'RS_IN_INVALID_STATUS', 'child is invalid.'

    rv = client.patch(f"/api/v1/fas/routing-slips/{parent.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.WRITE_OFF_REQUESTED.value}), headers=headers)
    assert rv.status_code == 200, 'status changed successfully.'

    # link them together ,success cases
    data = {'childRoutingSlipNumber': f"{child1.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == 'RS_IN_INVALID_STATUS', 'parent is invalid.'


def test_link_routing_slip(session, client, jwt, app):
    """Assert that the linking of routing slip works as expected."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value,
                                             Role.FAS_SEARCH.value, Role.FAS_EDIT.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    child = get_routing_slip_request('206380834')
    parent = get_routing_slip_request('206380867')
    paid_amount_child = child.get('payments')[0].get('paidAmount')
    paid_amount_parent = parent.get('payments')[0].get('paidAmount')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent), headers=headers)

    rv = client.get(f"/api/v1/fas/routing-slips/{child.get('number')}/links", headers=headers)
    assert rv.json.get('parent') is None

    # attempt to link NSF, should fail
    nsf = get_routing_slip_request('933458069')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(nsf), headers=headers)
    rv = client.patch(f'/api/v1/fas/routing-slips/{nsf.get("number")}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.NSF.value}), headers=headers)

    data = {'childRoutingSlipNumber': f"{nsf.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_CANT_LINK_NSF'
    assert rv.status_code == 400

    # link them together ,success cases
    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('status') == 'LINKED'
    assert rv.json.get('remainingAmount') == 0
    assert rv.json.get('total') == paid_amount_child

    rv = client.get(f"/api/v1/fas/routing-slips/{child.get('number')}/links", headers=headers)
    assert rv.json.get('parent') is not None
    assert rv.json.get('parent').get('number') == parent.get('number')
    assert rv.json.get('parent').get('remainingAmount') == paid_amount_child + \
        paid_amount_parent
    assert rv.json.get('parent').get('total') == paid_amount_parent

    rv = client.get(f"/api/v1/fas/routing-slips/{parent.get('number')}/links", headers=headers)
    assert len(rv.json.get('children')) == 1
    assert rv.json.get('children')[0].get('number') == child.get('number')

    # assert errors
    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_ALREADY_LINKED'
    assert rv.status_code == 400

    # assert errors
    data = {'childRoutingSlipNumber': f"{parent.get('number')}", 'parentRoutingSlipNumber': f"{child.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_ALREADY_A_PARENT'
    assert rv.status_code == 400

    # assert transactions
    child = get_routing_slip_request(number='206380859')
    parent = get_routing_slip_request(number='206380891')
    rv1 = client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    rv2 = client.post('/api/v1/fas/routing-slips', data=json.dumps(parent), headers=headers)
    payment_account_id = rv1.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    folio_number = 'test_folio'
    invoice = factory_invoice(payment_account, folio_number=folio_number, routing_slip=rv1.json.get('number'),
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()
    # assert errors
    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_CHILD_HAS_TRANSACTIONS'
    assert rv.status_code == 400

    payment_account_id = rv2.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    invoice2 = factory_invoice(payment_account, folio_number=folio_number, routing_slip=rv2.json.get('number'),
                               payment_method_code=PaymentMethod.INTERNAL.value)
    invoice2.save()
    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_CHILD_HAS_TRANSACTIONS'
    assert rv.status_code == 400

    child1 = get_routing_slip_request(number='206380842')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child1), headers=headers)

    data = {'childRoutingSlipNumber': f"{child1.get('number')}", 'parentRoutingSlipNumber': f"{child1.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_CANT_LINK_TO_SAME'
    assert rv.status_code == 400

    # parent record can have transactions
    payment_account_id = rv2.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    invoice2 = factory_invoice(payment_account, folio_number=folio_number, routing_slip=rv2.json.get('number'),
                               payment_method_code=PaymentMethod.INTERNAL.value)
    invoice2.save()
    data = {'childRoutingSlipNumber': f"{child1.get('number')}", 'parentRoutingSlipNumber': f"{parent.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.status_code == 200, 'parent can have transactions'


def test_create_routing_slips_search_with_folio_number(session, client, jwt, app):
    """Assert that the search works."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request(number='206380792')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    payment_account_id = rv.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    folio_number = 'test_folio'
    invoice = factory_invoice(payment_account, folio_number=folio_number, routing_slip=rv.json.get('number'),
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()

    # search with routing slip number works

    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'routingSlipNumber': rv.json.get('number'), 'folioNumber': folio_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1, 'folio and routing slip combo works.'

    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'folioNumber': folio_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1, 'folio alone works.'

    # create another routing slip with folo

    payload = get_routing_slip_request(number='206380867')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    payment_account_id = rv.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    routing_slip_numbr = rv.json.get('number')
    invoice = factory_invoice(payment_account, folio_number=folio_number, routing_slip=routing_slip_numbr,
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()

    invoice = factory_invoice(payment_account, folio_number=folio_number, routing_slip=rv.json.get('number'),
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()

    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'folioNumber': folio_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 2, 'folio alone works.'

    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'routingSlipNumber': routing_slip_numbr, 'folioNumber': folio_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1, 'folio and rs fetches only 1.'
    assert len(items[0].get('invoices')) == 2, 'fetches all the folios. UI wil filter it out'

    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'routingSlipNumber': routing_slip_numbr}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1, 'folio and rs fetches only 1.'
    assert len(items[0].get('invoices')) == 2, 'folio alone works.'


def test_create_routing_slips_search_with_receipt(session, client, jwt, app):
    """Assert that the search works."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request(number='206380909')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    receipt_number = payload.get('payments')[0].get('chequeReceiptNumber')
    # search with routing slip number works
    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'chequeReceiptNumber': receipt_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('payments')[0].get('chequeReceiptNumber') == receipt_number

    # search with routing slip number works
    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'receiptNumber': receipt_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 0

    # search with routing slip number works
    rv = client.post('/api/v1/fas/routing-slips/queries',
                     data=json.dumps({'chequeReceiptNumber': receipt_number, 'receiptNumber': receipt_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 0

    # search with entity (accountName) works
    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'accountName': 'TEST'}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1

    payload = get_routing_slip_request(number='674038203',
                                       cheque_receipt_numbers=[('211001', PaymentMethod.CASH.value, 100)])

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201

    receipt_number = payload.get('payments')[0].get('chequeReceiptNumber')
    # search with routing slip number works
    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'receiptNumber': receipt_number}),
                     headers=headers)

    items = rv.json.get('items')
    assert len(items) == 1
    assert items[0].get('payments')[0].get('chequeReceiptNumber') == receipt_number


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(number='559555333'),
])
def test_create_routing_slips_unauthorized(session, client, jwt, payload):
    """Assert that the endpoint returns 401 for users with no fas_editor role."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_USER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 401


"""
Example valid routing slip numbers:
206380792, 206380800, 206380818, 206380826
206380834, 206380842, 206380859, 206380867
206380875, 206380883, 206380891, 206380909
"""


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(number='559555333'),
])
def test_create_routing_slips_invalid_digits(session, client, jwt, payload):
    """Assert POST returns 400 when providing invalid routing slip number."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_USER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    current_app.config['ALLOW_LEGACY_ROUTING_SLIPS'] = False
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400
    current_app.config['ALLOW_LEGACY_ROUTING_SLIPS'] = True


def test_get_routing_slips_invalid_digits(session, client, jwt, app):
    """Assert GET returns 400 when providing invalid routing slip number."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_VIEW.value, Role.FAS_CREATE.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    current_app.config['ALLOW_LEGACY_ROUTING_SLIPS'] = False
    rv = client.get('/api/v1/fas/routing-slips/206380555', headers=headers)
    assert rv.status_code == 400
    current_app.config['ALLOW_LEGACY_ROUTING_SLIPS'] = True


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(number='206380883'),
])
def test_routing_slips_for_errors(session, client, jwt, payload):
    """Assert that the endpoint returns 401 for users with no fas_editor role."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
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

    # Get a routing slip which doesn't exist and assert 204
    rv = client.get('/api/v1/fas/routing-slips/206380891', headers=headers)
    assert rv.status_code == 204


def test_update_routing_slip_status(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_EDIT.value, Role.FAS_VIEW.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    rs_number = rv.json.get('number')

    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.COMPLETE.value}), headers=headers)
    assert rv.status_code == 400

    # Update to NSF and validate the total
    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.NSF.value}), headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('status') == RoutingSlipStatus.NSF.value
    assert rv.json.get('remainingAmount') == 0

    # assert invalid action.
    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action=TEST',
                      data=json.dumps({'status': RoutingSlipStatus.ACTIVE.value}), headers=headers)
    assert rv.status_code == 400

    # Assert invalid number
    rv = client.patch(f'/api/v1/fas/routing-slips/TEST?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.ACTIVE.value}), headers=headers)
    assert rv.status_code == 400


def test_routing_slip_report(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_REPORTS.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/fas/routing-slips/{datetime.now().strftime(DT_SHORT_FORMAT)}/reports', headers=headers)
    assert rv.status_code == 201


def test_create_comment_with_valid_routing_slips(session, client, jwt):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rv.json.get('number')),
                     data=json.dumps({'comment': 'test'}),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('submitterDisplayName')


def test_create_comment_with_invalid_routing_slips(session, client, jwt):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format('invalid_routing_slip_number'),
                     data=json.dumps({'comment': 'test'}),
                     headers=headers)
    assert rv.json.get('type') == 'FAS_INVALID_ROUTING_SLIP_NUMBER'
    assert rv.status_code == 400


def test_create_comment_with_invalid_body_request(session, client, jwt):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format('invalid_routing_slip_number'),
                     data=json.dumps({'comment_invalid': 'test'}),
                     headers=headers)
    assert rv.json.get('type') == 'INVALID_REQUEST'
    assert rv.status_code == 400


def test_create_comment_with_valid_comment_schema(session, client, jwt):
    """Assert that the endpoint returns 201 for valid comment schema."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rv.json.get('number')),
                     data=json.dumps({'comment': 'test'}),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('submitterDisplayName')


def test_create_comment_with_invalid_comment_schema(session, client, jwt):
    """Assert that the endpoint returns 400 for invalid comment schema."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rv.json.get('number')),
                     data=json.dumps({'test': 'test'}),
                     headers=headers)
    assert rv.json.get('type') == 'INVALID_REQUEST'
    assert rv.status_code == 400


def test_create_comment_with_valid_comment_bcrs_schema(session, client, jwt):
    """Assert that the endpoint returns 201 for valid comment schema."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rv.json.get('number')),
                     data=json.dumps({'comment': {'businessId': 'test', 'comment': 'test'}}),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('submitterDisplayName')


def test_create_comment_with_invalid_comment_bcrs_schema(session, client, jwt):
    """Assert that the endpoint returns 201 for valid comment schema."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rv.json.get('number')),
                     data=json.dumps({'comment': {'businessId': 'test'}}),
                     headers=headers)
    assert rv.json.get('type') == 'INVALID_REQUEST'
    assert rv.status_code == 400


def test_get_valid_comments(session, client, jwt):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)

    rs_number = rv.json.get('number')

    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rs_number),
                     data=json.dumps({'comment': 'test_1'}),
                     headers=headers)
    rv = client.post('/api/v1/fas/routing-slips/{}/comments'.format(rs_number),
                     data=json.dumps({'comment': 'test_2'}),
                     headers=headers)

    rv = client.get('/api/v1/fas/routing-slips/{}/comments'.format(rs_number), headers=headers)
    assert rv.status_code == 200
    items = rv.json.get('comments')
    assert len(items) == 2
    assert items[0].get('comment') == 'test_2'
    assert items[1].get('comment') == 'test_1'
    assert items[0].get('submitterDisplayName')
    assert items[1].get('submitterDisplayName')

    rv = client.get('/api/v1/fas/routing-slips/{}/comments'.format('invalid'), headers=headers)
    assert rv.json.get('type') == 'FAS_INVALID_ROUTING_SLIP_NUMBER'
    assert rv.status_code == 400


def test_get_invalid_comments(session, client, jwt):
    """Assert that the endpoint returns 400 based on conditions."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.get('/api/v1/fas/routing-slips/{}/comments'.format('invalid'), headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == 'FAS_INVALID_ROUTING_SLIP_NUMBER'


def test_create_routing_slips_invalid_number(session, client, jwt, app):
    """Assert that the rs number validation works."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request(number='123456')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request(number='1234567891')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400


def test_update_routing_slip_writeoff(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_EDIT.value, Role.FAS_VIEW.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(get_routing_slip_request()), headers=headers)
    rs_number = rv.json.get('number')

    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.WRITE_OFF_REQUESTED.value}), headers=headers)
    assert rv.status_code == 200

    # Update to WRITEOFF_AUTHORIZED and assert 400, as it's a same token
    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value}), headers=headers)
    assert rv.status_code == 400

    # Try CANCEL WRITE_OFF with a supervisor token and assert 200.
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_EDIT.value,
                                             Role.FAS_REFUND_APPROVER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.patch(f'/api/v1/fas/routing-slips/{rs_number}?action={PatchActions.UPDATE_STATUS.value}',
                      data=json.dumps({'status': RoutingSlipCustomStatus.CANCEL_WRITE_OFF_REQUEST.custom_status}),
                      headers=headers)
    assert rv.status_code == 200


def test_create_routing_slip_null_cheque_date(session, client, jwt, app):
    """Assert that the endpoint returns invalid request for null payment date."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_EDIT.value, Role.FAS_VIEW.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    routing_slip_payload: Dict[str, any] = {
        'number': '345777543',
        'routingSlipDate': datetime.now().strftime(DT_SHORT_FORMAT),
        'paymentAccount': {
            'accountName': 'TEST'
        },
        'payments': []
    }
    routing_slip_payload['payments'].append({
        'paymentMethod': PaymentMethod.CHEQUE.value,
        'chequeReceiptNumber': '1234567890',
        'paidAmount': 100
    })

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(routing_slip_payload), headers=headers)
    assert rv.status_code == 400


def test_routing_slip_link_attempt(session, client, jwt, app):
    """12033 - Scenario 3.

    Routing slip is Completed, attempt to be linked.
    Linking shouldn't be allowed and explaining that completed routing
    slip cannot be involved in linking.
    """
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value, Role.FAS_SEARCH.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    child = get_routing_slip_request('438607657')
    parent1 = get_routing_slip_request('355336710')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent1), headers=headers)

    rs_model = RoutingSlip.find_by_number('438607657')
    rs_model.status = RoutingSlipStatus.COMPLETE.value
    rs_model.commit()

    data = {'childRoutingSlipNumber': f"{child.get('number')}", 'parentRoutingSlipNumber': f"{parent1.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_IN_INVALID_STATUS'
    assert rv.status_code == 400

    # Try the reverse:
    data = {'childRoutingSlipNumber': f"{parent1.get('number')}", 'parentRoutingSlipNumber': f"{child.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_IN_INVALID_STATUS'
    assert rv.status_code == 400


def test_routing_slip_status_to_nsf_attempt(session, client, jwt, app):
    """12033 - Scenario 4.

    Routing slip in Completed,
    user attempts to move it into another status, can only set to NSF.
    """
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value,
                                             Role.FAS_SEARCH.value, Role.FAS_EDIT.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    child = get_routing_slip_request('438607657')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)

    rs_model = RoutingSlip.find_by_number('438607657')
    rs_model.status = RoutingSlipStatus.COMPLETE.value
    rs_model.commit()

    # Active shouldn't work.
    rv = client.patch(f"/api/v1/fas/routing-slips/{child.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.ACTIVE.value}), headers=headers)
    assert rv.status_code == 400

    # NSF should work.
    rv = client.patch(f"/api/v1/fas/routing-slips/{child.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.NSF.value}), headers=headers)
    assert rv.status_code == 200, 'status changed successfully.'


def test_routing_slip_void(session, client, jwt, app):
    """For testing void routing slips."""
    # Create routing slip.
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value,
                                             Role.FAS_SEARCH.value, Role.FAS_EDIT.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rs = get_routing_slip_request('438607657')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(rs), headers=headers)

    # Create invoice.
    invoice = factory_invoice(PaymentAccount(id=rv.json.get('paymentAccount').get('id')), folio_number='test_folio',
                              routing_slip=rv.json.get('number'),
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()

    # No permissions
    rv = client.patch(f"/api/v1/fas/routing-slips/{rs.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.VOID.value}), headers=headers)
    assert rv.status_code == 403

    token = jwt.create_jwt(get_claims(roles=[Role.FAS_EDIT.value, Role.FAS_VOID.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Has transactions
    rv = client.patch(f"/api/v1/fas/routing-slips/{rs.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.VOID.value}), headers=headers)
    assert rv.json.get('type') == 'RS_HAS_TRANSACTIONS'
    assert rv.status_code == 400

    invoice.routing_slip = None
    invoice.save()

    # Success case
    rv = client.patch(f"/api/v1/fas/routing-slips/{rs.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.VOID.value}), headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('remainingAmount') == 0


def test_routing_slip_correction(session, client, jwt, app):
    """For testing correction of routing slips."""
    # Create routing slip.
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value,
                                             Role.FAS_SEARCH.value, Role.FAS_EDIT.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rs = get_routing_slip_request('438607657')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(rs), headers=headers)
    payment_id = rv.json.get('payments')[0].get('id')
    assert payment_id

    # Create invoice.
    invoice = factory_invoice(PaymentAccount(id=rv.json.get('paymentAccount').get('id')), folio_number='test_folio',
                              routing_slip=rv.json.get('number'),
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()

    # Failure case, no permissions
    rv = client.patch(f"/api/v1/fas/routing-slips/{rs.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.CORRECTION.value}), headers=headers)
    assert rv.status_code == 403

    token = jwt.create_jwt(get_claims(roles=[Role.FAS_VIEW.value, Role.FAS_EDIT.value, Role.FAS_CORRECTION.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Failure case, no payments.
    rv = client.patch(f"/api/v1/fas/routing-slips/{rs.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps({'status': RoutingSlipStatus.CORRECTION.value}), headers=headers)
    assert rv.status_code == 400

    # Success case
    payload = {
        'status': RoutingSlipStatus.CORRECTION.value,
        'payments': [
            {
                'id': payment_id,
                'paidAmount': 50,
                'paidUsdAmount': 50,
                'chequeReceiptNumber': '911'
            }
        ]
    }

    rv = client.patch(f"/api/v1/fas/routing-slips/{rs.get('number')}?action={PatchActions.UPDATE_STATUS.value}",
                      data=json.dumps(payload), headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('total') == 50
    assert rv.json.get('remainingAmount') == 50
    assert rv.json.get('status') == RoutingSlipStatus.ACTIVE.value  # Active here, because we have no CFS account.
    assert rv.json.get('payments')
    assert rv.json.get('payments')[0].get('paidAmount') == 50
    assert rv.json.get('payments')[0].get('paidUsdAmount') == 50
    assert rv.json.get('payments')[0].get('chequeReceiptNumber') == '911'

    rv = client.get(f"/api/v1/fas/routing-slips/{rs.get('number')}/comments", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('comments')
