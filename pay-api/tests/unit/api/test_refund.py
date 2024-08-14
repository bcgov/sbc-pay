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

"""Tests to assure the receipt end-point.

Test-Suite to ensure that the /receipt endpoint is working as expected.
"""
from decimal import Decimal
import json

from datetime import datetime, timezone

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Refund as RefundModel
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, Role
from pay_api.utils.errors import Error
from tests.utilities.base_test import (
    factory_invoice_reference, get_claims, get_payment_request, get_payment_request_with_payment_method,
    get_payment_request_with_service_fees, get_routing_slip_request, get_unlinked_pad_account_payload, token_header)
from unittest.mock import patch


def test_create_refund(session, client, jwt, app, monkeypatch):
    """Assert that the endpoint  returns 202."""
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

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['DIRECT_PAY.PAID']
    assert RefundModel.find_by_invoice_id(inv_id) is not None


def test_create_drawdown_refund(session, client, jwt, app):
    """Assert that the endpoint returns 202."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(
                         get_payment_request_with_payment_method(
                             business_identifier='CP0002000', payment_method='DRAWDOWN'
                         )
                     ),
                     headers=headers)
    inv_id = rv.json.get('id')

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['DIRECT_PAY.PAID']


def test_create_eft_refund(session, client, jwt, app):
    """Assert EFT refunds work."""
    with patch('pay_api.services.eft_service.datetime') as mock_date:
        # After 6 PM
        mock_date.now.return_value = datetime(2024, 1, 1, 19, 0)
        mock_date.side_effect = lambda *args, **kw: datetime(*args, **kw)

        token = jwt.create_jwt(get_claims(), token_header)
        headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

        rv = client.post(
            '/api/v1/payment-requests',
            data=json.dumps(
                get_payment_request_with_payment_method(
                    business_identifier='CP0002000',
                    payment_method='EFT')),
            headers=headers)

        inv_id = rv.json.get('id')

        rv = client.post(
            '/api/v1/payment-requests',
            data=json.dumps(
                get_payment_request_with_payment_method(
                    business_identifier='CP0002000',
                    payment_method='EFT')),
            headers=headers)

        inv_id2 = rv.json.get('id')
        factory_invoice_reference(inv_id2, 'REG3904393').save()
        token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
        headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
        rv = client.post(
            f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
            headers=headers)
        rv = client.post(
            f'/api/v1/payment-requests/{inv_id2}/refunds', data=json.dumps({'reason': 'Test'}),
            headers=headers)

        invoice = InvoiceModel.find_by_id(inv_id)
        assert invoice.invoice_status_code == InvoiceStatus.CANCELLED.value

        invoice2 = InvoiceModel.find_by_id(inv_id2)
        assert invoice2.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

    with patch('pay_api.services.eft_service.datetime') as mock_date:
        # Before 6 PM
        mock_date.now.return_value = datetime(2024, 1, 1, 17, 0)
        mock_date.side_effect = lambda *args, **kw: datetime(*args, **kw)

        token = jwt.create_jwt(get_claims(), token_header)
        headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

        rv = client.post(
            '/api/v1/payment-requests',
            data=json.dumps(
                get_payment_request_with_payment_method(
                    business_identifier='CP0002000',
                    payment_method='EFT')),
            headers=headers)

        inv_id = rv.json.get('id')
        factory_invoice_reference(inv_id, 'REG3904393').save()
        token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
        headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
        rv = client.post(
            f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
            headers=headers)

        invoice2 = InvoiceModel.find_by_id(inv_id)
        assert invoice2.invoice_status_code == InvoiceStatus.CANCELLED.value


def test_create_pad_refund(session, client, jwt, app):
    """Assert that the endpoint returns 202 and creates a credit on the account."""
    # 1. Create a PAD payment_account and cfs_account.
    # 2. Create a PAD invoice and mark as PAID.
    # 3. Issue a refund and assert credit is reflected on payment_account.
    # 4. Create an invoice again and assert that credit is updated.
    auth_account_id = 1234

    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload(account_id=auth_account_id)),
                headers=headers)
    pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_account_id(pay_account.id)[0]
    cfs_account.cfs_party = '1111'
    cfs_account.cfs_account = '1111'
    cfs_account.cfs_site = '1111'
    cfs_account.status = CfsAccountStatus.ACTIVE.value
    cfs_account.save()

    pay_account.pad_activation_date = datetime.now(tz=timezone.utc)
    pay_account.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(
                         get_payment_request_with_payment_method(
                             payment_method=PaymentMethod.PAD.value
                         )
                     ),
                     headers=headers)

    inv_id = rv.json.get('id')
    inv_total = rv.json.get('total')

    inv: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    inv.invoice_status_code = InvoiceStatus.PAID.value
    inv.payment_date = datetime.now(tz=timezone.utc)
    inv.save()

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['PAD.PAID']

    # Assert credit is updated.
    pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    credit = pay_account.credit
    assert pay_account.credit == inv_total

    # Create an invoice again and assert that credit is updated.
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(
                         get_payment_request_with_service_fees(corp_type='CP',
                                                               filing_type='OTADD'
                                                               )
                     ),
                     headers=headers)
    assert rv.status_code == 201
    inv_total = rv.json.get('total')

    pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    credit -= Decimal(str(inv_total))
    assert pay_account.credit == credit

    # Create an invoice again and assert that credit is updated.
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(
                         get_payment_request_with_payment_method(
                             payment_method=PaymentMethod.PAD.value
                         )
                     ),
                     headers=headers)
    assert rv.status_code == 201
    inv_total = rv.json.get('total')
    # Credit must be zero now as the new invoice amount exceeds remaining credit.
    assert pay_account.credit == 0


def test_create_duplicate_refund_fails(session, client, jwt, app):
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

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test 2'}),
                     headers=headers)
    assert rv.status_code == 400


def test_create_refund_with_existing_routing_slip(session, client,
                                                  jwt, app):
    """Assert that the endpoint  returns 202."""
    claims = get_claims(
        roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value, Role.FAS_REFUND.value, Role.STAFF.value, 'make_payment'])
    token = jwt.create_jwt(claims, token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = get_routing_slip_request()
    routingslip_amount = payload.get('payments')[0].get('paidAmount')
    rv = client.post('/api/v1/fas/routing-slips', data=json.dumps(payload), headers=headers)
    rs_number = rv.json.get('number')

    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    data = get_payment_request()
    data['accountInfo'] = {'routingSlip': rs_number}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    inv_id = rv.json.get('id')
    total = rv.json.get('total')
    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'routingSlipNumber': rs_number}),
                     headers=headers)
    items = rv.json.get('items')

    inv: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    inv.invoice_status_code = InvoiceStatus.PAID.value
    inv.payment_date = datetime.now(tz=timezone.utc)
    inv.save()

    assert items[0].get('remainingAmount') == payload.get('payments')[0].get('paidAmount') - total

    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['INTERNAL.REFUND_REQUESTED']

    rv = client.post('/api/v1/fas/routing-slips/queries', data=json.dumps({'routingSlipNumber': rs_number}),
                     headers=headers)
    # asssert refund amount goes to routing slip back
    assert rv.json.get('items')[0].get('remainingAmount') == routingslip_amount


def test_create_refund_with_legacy_routing_slip(session, client,
                                                jwt, app):
    """Assert that the endpoint returns 400."""
    claims = get_claims(
        roles=[Role.FAS_CREATE.value, Role.FAS_SEARCH.value, Role.FAS_REFUND.value, Role.STAFF.value, 'make_payment'])
    token = jwt.create_jwt(claims, token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    data = get_payment_request()
    data['accountInfo'] = {'routingSlip': 'legacy_number'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    inv_id = rv.json.get('id')

    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == 'ROUTING_SLIP_REFUND'


def test_create_refund_fails(session, client, jwt, app, monkeypatch):
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

    invoice = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.APPROVED.value
    invoice.save()

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds', data=json.dumps({'reason': 'Test'}),
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == Error.INVALID_REQUEST.name
    assert RefundModel.find_by_invoice_id(inv_id) is None
