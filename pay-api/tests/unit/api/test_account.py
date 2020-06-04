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

from pay_api.models.credit_payment_account import CreditPaymentAccount
from pay_api.models.payment import Payment
from pay_api.models.payment_account import PaymentAccount
from pay_api.schemas import utils as schema_utils
from tests.utilities.base_test import (
    get_claims, get_payment_request, token_header)


def test_account_purchase_history(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/queries', data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 200


def test_account_purchase_history_pagination(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    for i in range(10):
        rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

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

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

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

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

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

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

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

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

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

    payment: Payment = Payment.find_by_id(rv.json.get('id'))
    credit_account: CreditPaymentAccount = CreditPaymentAccount.find_by_id(payment.invoices[0].credit_account_id)
    pay_account: PaymentAccount = PaymentAccount.find_by_id(credit_account.account_id)

    rv = client.post(f'/api/v1/accounts/{pay_account.auth_account_id}/payments/queries',
                     data=json.dumps({}),
                     headers=headers)

    assert rv.status_code == 200
    # Assert the total is coming as 10 which is the value of default TRANSACTION_REPORT_DEFAULT_TOTAL
    assert rv.json.get('total') == 10
