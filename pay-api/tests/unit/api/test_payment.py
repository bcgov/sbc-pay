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
from unittest.mock import patch

from requests.exceptions import ConnectionError

from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import Role
from tests.utilities.base_test import (
    factory_payment_transaction, get_claims, get_payment_request, get_payment_request_with_folio_number,
    get_payment_request_with_no_contact_info, get_payment_request_with_payment_method, get_waive_fees_payment_request,
    get_zero_dollar_payment_request, token_header)


def test_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_payment_creation_with_service_account(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value, Role.EDITOR.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_with_payment_method()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_payment_creation_service_account_with_no_edit_role(session, client, jwt, app):
    """Assert that the endpoint returns 403."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)
    assert rv.status_code == 403


def test_payment_creation_for_unauthorized_user(session, client, jwt, app):
    """Assert that the endpoint returns 403."""
    token = jwt.create_jwt(get_claims(username='TEST', login_source='PASSCODE'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0000000')),
                     headers=headers)
    assert rv.status_code == 403


def test_payment_incomplete_input(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    data = {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': 'CP0001234',
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
    rv = client.post('/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_payment_invalid_corp_type(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    data = {
        'businessInfo': {
            'businessIdentifier': 'CP0001234',
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
    rv = client.post('/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_payment_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
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

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()

    rv = client.put(f'/api/v1/payment-requests/{pay_id}', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 200


def test_payment_put_incomplete_input(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()

    data = {
        'businessInfo': {
            'businessIdentifier': 'CP0001234',
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
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_payment_put_invalid_corp_type(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()

    data = {
        'businessInfo': {
            'businessIdentifier': 'CP0001234',
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
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_payment_creation_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
        assert rv.status_code == 400


def test_payment_put_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    transaction = factory_payment_transaction(pay_id)
    transaction.save()
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        rv = client.put(f'/api/v1/payment-requests/{pay_id}', data=json.dumps(get_payment_request()), headers=headers)
        assert rv.status_code == 400


def test_zero_dollar_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_zero_dollar_payment_request()),
                     headers=headers)

    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('statusCode', None) == 'COMPLETED'

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_zero_dollar_payment_creation_for_unaffiliated_entity(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_zero_dollar_payment_request(business_identifier='CP0001237')),
                     headers=headers)

    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('statusCode', None) == 'COMPLETED'

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_delete_payment(session, client, jwt, app):
    """Assert that the endpoint returns 204."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')
    rv = client.delete(f'/api/v1/payment-requests/{pay_id}', headers=headers)
    assert rv.status_code == 202


def test_delete_completed_payment(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_zero_dollar_payment_request()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('statusCode', None) == 'COMPLETED'

    pay_id = rv.json.get('id')
    rv = client.delete(f'/api/v1/payment-requests/{pay_id}', headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_payment_delete_when_paybc_is_down(session, client, jwt, app):
    """Assert that the endpoint returns 202. The payment will be acceoted to delete."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    pay_id = rv.json.get('id')

    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
        rv = client.delete(f'/api/v1/payment-requests/{pay_id}', headers=headers)
        assert rv.status_code == 202


def test_payment_creation_with_routing_slip(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    data = get_payment_request()
    data['accountInfo'] = {'routingSlip': 'TEST_ROUTE_SLIP'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('invoices')[0].get('routingSlip') == 'TEST_ROUTE_SLIP'

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_bcol_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = {
        'businessInfo': {
            'businessIdentifier': 'CP0002000',
            'corpType': 'CP',
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
            ],
            'folioNumber': 'TEST'
        }
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_zero_dollar_payment_creation_with_waive_fees(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_waive_fees_payment_request()),
                     headers=headers)

    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('statusCode', None) == 'COMPLETED'
    assert rv.json.get('paymentSystem', None) == 'INTERNAL'
    assert rv.json.get('invoices')[0].get('total') == 0
    assert rv.json.get('invoices')[0].get('total') == 0

    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_zero_dollar_payment_creation_with_waive_fees_unauthorized(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_waive_fees_payment_request()),
                     headers=headers)

    assert rv.status_code == 401
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_premium_payment_creation(session, client, jwt, app, premium_user_mock):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'payment_response')[0]


def test_premium_payment_creation_with_payment_method(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_payment_method(business_identifier='CP0002000', payment_method='DRAWDOWN')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'payment_response')[0]
    assert rv.json.get('paymentSystem') == 'BCOL'


def test_cc_payment_with_no_contact_info(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1234'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(payment_method='CC', corp_type='PPR')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'payment_response')[0]
    assert rv.json.get('paymentSystem') == 'PAYBC'


def test_premium_payment_with_no_contact_info(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1234'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(payment_method='DRAWDOWN', corp_type='PPR')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'payment_response')[0]
    assert rv.json.get('paymentSystem') == 'BCOL'


def test_payment_creation_with_folio_number(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    folio_number = '1234567890'

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_payment_request_with_folio_number(folio_number=folio_number)),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'payment_response')[0]
    assert rv.json.get('invoices')[0].get('folioNumber') == folio_number

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_payment_request()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'payment_response')[0]
    assert rv.json.get('invoices')[0].get('folioNumber') == 'MOCK1234'
