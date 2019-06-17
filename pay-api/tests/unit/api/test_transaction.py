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

"""Tests to assure the transactions end-point.

Test-Suite to ensure that the /transactions endpoint is working as expected.
"""

import json
import uuid

from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import Role


token_header = {
    'alg': 'RS256',
    'typ': 'JWT',
    'kid': 'sbc-auth-cron-job'
}


def get_claims(role: str = Role.BASIC.value):
    """Return the claim with the role param."""
    claim = {
        'jti': 'a50fafa4-c4d6-4a9b-9e51-1e5e0d102878',
        'exp': 31531718745,
        'iat': 1531718745,
        'iss': 'https://sso-dev.pathfinder.gov.bc.ca/auth/realms/fcf0kpqr',
        'aud': 'sbc-auth-web',
        'sub': '15099883-3c3f-4b4c-a124-a1824d6cba84',
        'typ': 'Bearer',
        'realm_access':
            {
                'roles':
                    [
                        '{}'.format(role)
                    ]
            },
        'preferred_username': 'test'
    }
    return claim


def test_transaction_post(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('payment_id') == payment_id
    assert schema_utils.validate(rv.json, 'transaction')[0]


def test_transaction_post_no_redirect_uri(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions', data=None,
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY007'


def test_transactions_post_invalid_payment(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payment_id = 9999
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions', data=None,
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY007'


def test_transaction_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.get(f'/api/v1/payments/{payment_id}/transactions/{txn_id}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('payment_id') == payment_id
    assert rv.json.get('id') == txn_id
    assert schema_utils.validate(rv.json, 'transaction')[0]


def test_transaction_get_invalid_payment_and_transaction(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    txn_id = rv.json.get('id')
    invalid_payment_id = 999
    rv = client.get(f'/api/v1/payments/{invalid_payment_id}/transactions/{txn_id}', headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY008'
    invalid_txn_id = uuid.uuid4()
    rv = client.get(f'/api/v1/payments/{payment_id}/transactions/{invalid_txn_id}', headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY008'


def test_transaction_put(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.put(f'/api/v1/payments/{payment_id}/transactions/{txn_id}?receipt_number={receipt_number}', data=None,
                    headers=headers)
    assert rv.status_code == 200


def test_transaction_put_with_no_receipt(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.put(f'/api/v1/payments/{payment_id}/transactions/{txn_id}', data=None,
                    headers=headers)
    assert rv.status_code == 200


def test_transaction_put_completed_payment(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)
    payment_id = rv.json.get('id')
    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    rv = client.post(f'/api/v1/payments/{payment_id}/transactions?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    print(rv.json)

    txn_id = rv.json.get('id')
    rv = client.put(f'/api/v1/payments/{payment_id}/transactions/{txn_id}', data=None,
                    headers=headers)
    print(rv.json)

    rv = client.put(f'/api/v1/payments/{payment_id}/transactions/{txn_id}', data=None,
                    headers=headers)
    print(rv.json)

    assert rv.status_code == 400
    assert rv.json.get('code') == 'PAY006'


def test_transactions_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Create a payment first
    data = {
        'payment_info': {
            'method_of_payment': 'CC'
        },
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filing_info': {
            'filing_types': [
                {
                    'filing_type_code': 'OTADD',
                    'filing_description': 'TEST'
                },
                {
                    'filing_type_code': 'OTANN'
                }
            ]
        }
    }
    rv = client.post(f'/api/v1/payments', data=json.dumps(data), headers=headers)

    transactions_link = rv.json.get('_links').get('transactions')
    rv = client.get(f'{transactions_link}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('items') is not None
    assert len(rv.json.get('items')) == 0

    redirect_uri = 'http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd'
    rv = client.post(f'{transactions_link}?redirect_uri={redirect_uri}', data=None,
                     headers=headers)
    txn_id = rv.json.get('id')
    rv = client.get(f'{transactions_link}/{txn_id}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('id') == txn_id

    rv = client.get(f'{transactions_link}', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('items') is not None
    assert len(rv.json.get('items')) == 1

    assert schema_utils.validate(rv.json, 'transactions')[0]
