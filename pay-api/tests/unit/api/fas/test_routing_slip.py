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
from datetime import date, datetime, timedelta

from faker import Faker
import pytest

from pay_api.models import PaymentAccount
from pay_api.schemas import utils as schema_utils
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import PatchActions, PaymentMethod, Role, RoutingSlipStatus
from tests.utilities.base_test import factory_invoice, get_claims, get_routing_slip_request, token_header

fake = Faker()


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
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert schema_utils.validate(rv.json, 'routing_slip')[0]
    rv = client.get('/api/v1/fas/routing-slips/{}'.format(rv.json.get('number')), headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'routing_slip')[0]


def test_create_routing_slips_search(session, client, jwt, app):
    """Assert that the search works."""
    claims = get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value])
    token = jwt.create_jwt(claims, token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request()
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


def test_link_routing_slip(session, client, jwt, app):
    """Assert that the linking of routing slip works as expected."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_LINK.value, Role.FAS_SEARCH.value]),
                           token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    child = get_routing_slip_request()
    parent = get_routing_slip_request(number=fake.name())
    paid_amount_child = child.get('payments')[0].get('paidAmount')
    paid_amount_parent = parent.get('payments')[0].get('paidAmount')
    client.post('/api/v1/fas/routing-slips', data=json.dumps(child), headers=headers)
    client.post('/api/v1/fas/routing-slips', data=json.dumps(parent), headers=headers)

    rv = client.get(f"/api/v1/fas/routing-slips/{child.get('number')}/links", headers=headers)
    assert rv.json.get('parent') is None

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
    assert rv.json.get('type') == 'RS_ALREADY_HAS_A_PARENT'
    assert rv.status_code == 400

    # assert errors
    data = {'childRoutingSlipNumber': f"{parent.get('number')}", 'parentRoutingSlipNumber': f"{child.get('number')}"}
    rv = client.post('/api/v1/fas/routing-slips/links', data=json.dumps(data), headers=headers)
    assert rv.json.get('type') == 'RS_ALREADY_A_PARENT'
    assert rv.status_code == 400

    # assert transactions
    child = get_routing_slip_request(number=fake.name())
    parent = get_routing_slip_request(number=fake.name())
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
    assert rv.json.get('type') == 'RS_PARENT_HAS_TRANSACTIONS'
    assert rv.status_code == 400


def test_create_routing_slips_search_with_folio_number(session, client, jwt, app):
    """Assert that the search works."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request()
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    payment_account_id = rv.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    folio_number = 'test_folio'
    another_folio_number = 'another_test_folio'
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

    payload = get_routing_slip_request(number='99999')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    payment_account_id = rv.json.get('paymentAccount').get('id')
    payment_account = PaymentAccount(id=payment_account_id)
    routing_slip_numbr = rv.json.get('number')
    invoice = factory_invoice(payment_account, folio_number=folio_number, routing_slip=routing_slip_numbr,
                              payment_method_code=PaymentMethod.INTERNAL.value)
    invoice.save()

    invoice = factory_invoice(payment_account, folio_number=another_folio_number, routing_slip=rv.json.get('number'),
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
    payload = get_routing_slip_request()
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
    get_routing_slip_request(),
])
def test_create_routing_slips_unauthorized(session, client, jwt, app, payload):
    """Assert that the endpoint returns 401 for users with no fas_editor role."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_USER.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 401


@pytest.mark.parametrize('payload', [
    get_routing_slip_request(),
])
def test_routing_slips_for_errors(session, client, jwt, app, payload):
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
    rv = client.get('/api/v1/fas/routing-slips/5678987655678', headers=headers)
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


def test_routing_slip_report(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_REPORTS.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/fas/routing-slips/{datetime.now().strftime(DT_SHORT_FORMAT)}/reports', headers=headers)
    assert rv.status_code == 201
