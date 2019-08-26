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

"""Tests to assure the payments end-point.

Test-Suite to ensure that the /payments endpoint is working as expected.
"""

import json
from datetime import datetime
from unittest.mock import patch

from requests.exceptions import ConnectionError

from pay_api.models import PaymentTransaction
from pay_api.schemas import utils as schema_utils
from tests.utilities.base_test import get_claims, get_payment_request, token_header


def factory_payment_transaction(
        payment_id: str,
        status_code: str = 'DRAFT',
        client_system_url: str = 'http://google.com/',
        pay_system_url: str = 'http://google.com',
        transaction_start_time: datetime = datetime.now(),
        transaction_end_time: datetime = datetime.now(),
):
    """Factory."""
    return PaymentTransaction(
        payment_id=payment_id,
        status_code=status_code,
        client_system_url=client_system_url,
        pay_system_url=pay_system_url,
        transaction_start_time=transaction_start_time,
        transaction_end_time=transaction_end_time,
    )


def test_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_payment_incomplete_input(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    data = {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': 'CP1234',
            'corpType': 'CP',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        }
    }
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400


def test_payment_invalid_corp_type(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    data = {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': 'CP1234',
            'corpType': 'PC',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'OTADD',
                    'filingDescription': 'TEST'
                },
                {
                    'filingTypeCode': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400


def test_payment_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    rv = client.get(f'/api/v1/payment-requests/{pay_id}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_payment_get_exception(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    pay_id = '123456sdf'

    rv = client.get(f'/api/v1/payment-requests/{pay_id}', headers=headers)
    assert rv.status_code == 404

    pay_id = '9999999999'

    rv = client.get(f'/api/v1/payment-requests/{pay_id}', headers=headers)
    assert rv.status_code == 400


def test_payment_put(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()

    rv = client.put(f'/api/v1/payment-requests/{pay_id}', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 200


def test_payment_put_incomplete_input(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()

    data = {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': 'CP1234',
            'corpType': 'CP',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        }
    }
    rv = client.put(f'/api/v1/payment-requests/{pay_id}', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400


def test_payment_put_invalid_corp_type(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()

    data = {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': 'CP1234',
            'corpType': 'PC',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'OTADD',
                    'filingDescription': 'TEST'
                },
                {
                    'filingTypeCode': 'OTANN'
                }
            ]
        }
    }
    rv = client.put(f'/api/v1/payment-requests/{pay_id}', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400


def test_payment_creation_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
        assert rv.status_code == 400


def test_payment_put_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post(f'/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        rv = client.put(f'/api/v1/payment-requests/{pay_id}', data=json.dumps(get_payment_request()), headers=headers)
        assert rv.status_code == 400
