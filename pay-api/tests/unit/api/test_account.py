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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""

import json
from unittest.mock import patch

from requests.exceptions import ConnectionError

from pay_api.exceptions import ServiceUnavailableException
from pay_api.models.invoice import Invoice
from pay_api.models.payment_account import PaymentAccount
from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import Role, PaymentMethod
from tests.utilities.base_test import (
    get_claims, get_payment_request, get_basic_account_payload, get_premium_account_payload, token_header,
    get_unlinked_pad_account_payload)


def test_account_purchase_history(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/queries', data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 200


def test_account_purchase_history_pagination(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    for i in range(10):
        rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?page=1&limit=5',
                     data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 200
    assert rv.json.get('total') == 10
    assert len(rv.json.get('items')) == 5


def test_account_purchase_history_invalid_request(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    search_filter = {
        'businessIdentifier': 1111
    }

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?page=1&limit=5',
                     data=json.dumps(search_filter),
                     headers=headers)

    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_account_purchase_history_export_as_csv(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': 'text/csv'
    }

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/reports', data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 201


def test_account_purchase_history_export_as_pdf(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': 'application/pdf'
    }

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/reports', data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 201


def test_account_purchase_history_export_invalid_request(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': 'application/pdf'
    }

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/reports', data=json.dumps({
        'businessIdentifier': 1111
    }), headers=headers)

    assert rv.status_code == 400


def test_account_purchase_history_default_list(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create 11 payments
    for i in range(11):
        rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/queries',
                     data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 200
    # Assert the total is coming as 10 which is the value of default TRANSACTION_REPORT_DEFAULT_TOTAL
    assert rv.json.get('total') == 10


def test_basic_account_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/accounts', data=json.dumps(get_basic_account_payload()),
                     headers=headers)

    assert rv.status_code == 201


def test_basic_account_creation_unauthorized(session, client, jwt, app):
    """Assert that the endpoint returns 401."""
    token = jwt.create_jwt(get_claims(role=Role.EDITOR.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/accounts', data=json.dumps(get_basic_account_payload()),
                     headers=headers)

    assert rv.status_code == 401


def test_premium_account_creation(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/accounts', data=json.dumps(get_premium_account_payload()),
                     headers=headers)

    assert rv.status_code == 201


def test_premium_duplicate_account_creation(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    client.post('/api/v1/accounts', data=json.dumps(get_premium_account_payload()),
                headers=headers)

    rv = client.post('/api/v1/accounts', data=json.dumps(get_premium_account_payload()),
                     headers=headers)

    assert rv.status_code == 400


def test_premium_account_update(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/accounts', data=json.dumps(get_premium_account_payload()),
                     headers=headers)

    auth_account_id = rv.json.get('authAccountId')

    rv = client.get(f'/api/v1/accounts/{auth_account_id}', headers=headers)
    assert rv.json.get('authAccountId') == auth_account_id

    rv = client.put(f'/api/v1/accounts/{auth_account_id}', data=json.dumps(get_premium_account_payload()),
                    headers=headers)

    assert rv.status_code == 200


def test_premium_account_update_with_no_create(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    auth_account_id = 100000
    rv = client.put(f'/api/v1/accounts/{auth_account_id}',
                    data=json.dumps(get_premium_account_payload(account_id=auth_account_id)),
                    headers=headers)

    assert rv.status_code == 200


def test_create_pad_account_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Mock ServiceUnavailableException
    with patch('pay_api.services.oauth_service.OAuthService.post',
               side_effect=ServiceUnavailableException(ConnectionError('mocked error'))):
        rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload()),
                         headers=headers)

        assert rv.status_code == 202


def test_create_pad_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload()),
                     headers=headers)

    assert rv.status_code == 202


def test_create_online_banking_account_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Mock ServiceUnavailableException
    with patch('pay_api.services.oauth_service.OAuthService.post',
               side_effect=ServiceUnavailableException(ConnectionError('mocked error'))):
        rv = client.post('/api/v1/accounts',
                         data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                         headers=headers)

        assert rv.status_code == 202


def test_create_online_banking_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/accounts',
                     data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                     headers=headers)

    assert rv.status_code == 202


def test_create_pad_update_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Create account first
    rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload()), headers=headers)
    auth_account_id = rv.json.get('authAccountId')

    # Mock ServiceUnavailableException
    with patch('pay_api.services.oauth_service.OAuthService.post',
               side_effect=ServiceUnavailableException(ConnectionError('mocked error'))):
        rv = client.put(f'/api/v1/accounts/{auth_account_id}',
                        data=json.dumps(get_unlinked_pad_account_payload(bank_account='11111111')),
                        headers=headers)

        assert rv.status_code == 202


def test_update_pad_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload()), headers=headers)
    auth_account_id = rv.json.get('authAccountId')
    rv = client.put(f'/api/v1/accounts/{auth_account_id}',
                    data=json.dumps(get_unlinked_pad_account_payload(bank_account='11111111')),
                    headers=headers)

    assert rv.status_code == 202


def test_update_online_banking_account_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 200, as there is no CFS update."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/accounts',
                     data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')
    # Mock ServiceUnavailableException
    with patch('pay_api.services.oauth_service.OAuthService.post',
               side_effect=ServiceUnavailableException(ConnectionError('mocked error'))):
        rv = client.put(f'/api/v1/accounts/{auth_account_id}',
                        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                        headers=headers)

        assert rv.status_code == 202


def test_update_online_banking_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/accounts',
                     data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')
    rv = client.put(f'/api/v1/accounts/{auth_account_id}',
                    data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                    headers=headers)

    assert rv.status_code == 202
