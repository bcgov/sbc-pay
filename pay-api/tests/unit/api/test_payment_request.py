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

Test-Suite to ensure that the /payment-requests endpoint is working as expected.
"""

import json
from unittest.mock import patch

from flask import current_app
from requests.exceptions import ConnectionError

from pay_api.models import PaymentAccount as PaymentAccountModel, \
    DistributionCode as DistributionCodeModel
from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import PaymentMethod, Role, InvoiceStatus
from tests.utilities.base_test import (
    get_claims, get_payment_request, get_payment_request_with_folio_number,
    get_payment_request_with_service_fees,
    get_payment_request_with_no_contact_info, get_payment_request_with_payment_method, get_waive_fees_payment_request,
    get_zero_dollar_payment_request, token_header, get_basic_account_payload, get_unlinked_pad_account_payload,
    get_gov_account_payload, get_payment_request_for_wills, activate_pad_account)


def test_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_payment_creation_using_direct_pay(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    current_app.config['DIRECT_PAY_ENABLED'] = True
    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0001239')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'invoice')[0]
    assert rv.json.get('paymentMethod') == 'DIRECT_PAY'
    assert rv.json.get('isPaymentActionRequired')


def test_payment_creation_with_service_account(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value, Role.EDITOR.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_with_payment_method()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'invoice')[0]


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
    inv_id = rv.json.get('id')
    rv = client.get(f'/api/v1/payment-requests/{inv_id}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'invoice')[0]


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


def test_payment_creation_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1234'}

    # Create an account first with CC as preffered payment, and it will create a DIRECT_PAY account
    client.post('/api/v1/accounts', data=json.dumps(get_basic_account_payload(PaymentMethod.CC.value)), headers=headers)

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('isPaymentActionRequired')


def test_zero_dollar_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_zero_dollar_payment_request()),
                     headers=headers)

    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('statusCode', None) == 'COMPLETED'

    assert schema_utils.validate(rv.json, 'invoice')[0]


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

    assert schema_utils.validate(rv.json, 'invoice')[0]


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
    assert rv.json.get('routingSlip') == 'TEST_ROUTE_SLIP'

    assert schema_utils.validate(rv.json, 'invoice')[0]


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

    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_zero_dollar_payment_creation_with_waive_fees(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_waive_fees_payment_request()),
                     headers=headers)

    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('statusCode', None) == 'COMPLETED'
    assert rv.json.get('paymentMethod', None) == 'INTERNAL'
    assert rv.json.get('total') == 0
    assert rv.json.get('total') == 0

    assert schema_utils.validate(rv.json, 'invoice')[0]


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
    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_premium_payment_creation_with_payment_method(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_payment_method(business_identifier='CP0002000', payment_method='DRAWDOWN')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'invoice')[0]
    assert rv.json.get('paymentMethod') == 'DRAWDOWN'


def test_premium_payment_creation_with_payment_method_ob(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_payment_method(business_identifier='CP0002000', payment_method='ONLINE_BANKING')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('paymentMethod') == 'ONLINE_BANKING'
    invoice_id = rv.json.get('id')

    rv = client.patch(f'/api/v1/payment-requests/{invoice_id}', data=json.dumps(
        {'paymentInfo': {'methodOfPayment': 'CC'}}),
                      headers=headers)

    assert rv.status_code == 200
    assert rv.json.get('paymentMethod') == 'DIRECT_PAY'


def test_premium_payment_creation_with_payment_method_ob_cc(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_payment_method(business_identifier='CP0002000', payment_method='ONLINE_BANKING')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('paymentMethod') == 'ONLINE_BANKING'
    assert rv.json.get('isOnlineBankingAllowed')
    invoice_id = rv.json.get('id')

    rv = client.patch(f'/api/v1/payment-requests/{invoice_id}', data=json.dumps(
        {'paymentInfo': {'methodOfPayment': 'CC'}}),
                      headers=headers)

    assert rv.status_code == 200
    assert rv.json.get('paymentMethod') == 'DIRECT_PAY'

    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    rv = client.post(f'/api/v1/payment-requests/{invoice_id}/transactions', data=json.dumps(data),
                     headers={'content-type': 'application/json'})
    assert rv.status_code == 201


def test_cc_payment_with_no_contact_info(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1234'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(payment_method='CC', filing_type_code='OTANN')), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'invoice')[0]
    assert rv.json.get('paymentMethod') == 'CC'


def test_premium_payment_with_no_contact_info(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1234'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(payment_method='DRAWDOWN', corp_type='PPR')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert schema_utils.validate(rv.json, 'invoice')[0]
    assert rv.json.get('paymentMethod') == 'DRAWDOWN'


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

    assert schema_utils.validate(rv.json, 'invoice')[0]
    assert rv.json.get('folioNumber') == folio_number

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_payment_request()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None

    assert schema_utils.validate(rv.json, 'invoice')[0]
    assert rv.json.get('folioNumber') == 'MOCK1234'


def test_bcol_payment_creation_by_staff(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff', username='idir/tester', login_source='IDIR'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    dat_number: str = 'C1234567890'
    payload = {
        'accountInfo': {
            'datNumber': dat_number,
            'bcolAccountNumber': '000000'
        },
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
    assert rv.json.get('datNumber') == dat_number
    assert rv.json.get('paymentMethod') == 'DRAWDOWN'

    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_payment_creation_with_service_fees(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_with_service_fees()),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('serviceFees') > 0

    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_payment_creation_with_service_fees_for_zero_fees(session, client, jwt, app):
    """Assert that the service fee is zero if it's a free filing."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_payment_request_with_service_fees(filing_type='OTFDR')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('_links') is not None
    assert rv.json.get('serviceFees') == 0

    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_bcol_payment_creation_by_system(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=['system'], username='system tester', login_source=None), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    dat_number: str = 'C1234567890'
    payload = {
        'accountInfo': {
            'datNumber': dat_number,
            'bcolAccountNumber': '000000'
        },
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
    assert rv.json.get('datNumber') == dat_number
    assert rv.json.get('paymentMethod') == 'DRAWDOWN'

    assert not rv.json.get('isPaymentActionRequired')

    assert schema_utils.validate(rv.json, 'invoice')[0]


def test_invoice_pdf(session, client, jwt, app):
    """Test invoice pdf generation."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_payment_request_with_payment_method(
                         business_identifier='CP0002000', payment_method='ONLINE_BANKING'
                     )), headers=headers)
    invoice_id = rv.json.get('id')
    client.post(f'/api/v1/payment-requests/{invoice_id}/reports', headers=headers)
    assert True


def test_premium_payment_creation_with_ob_disabled(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(corp_type='NRO', filing_type_code='NM620',
                                                 payment_method='ONLINE_BANKING')),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('paymentMethod') == 'ONLINE_BANKING'
    assert not rv.json.get('isOnlineBankingAllowed')


def test_future_effective_premium_payment_creation_with_ob_disabled(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': '1'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(corp_type='BEN', filing_type_code='BCINC',
                                                 payment_method='ONLINE_BANKING', future_effective=True)),
                     headers=headers)
    assert rv.status_code == 201
    assert rv.json.get('paymentMethod') == 'ONLINE_BANKING'
    assert not rv.json.get('isOnlineBankingAllowed')


def test_create_pad_payment_request_when_account_is_pending(session, client, jwt, app):
    """Assert payment request works for PAD accounts."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Create account first
    rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload(account_id=1234)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(corp_type='BEN', filing_type_code='BCINC',
                                                 payment_method=PaymentMethod.PAD.value)),
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == 'ACCOUNT_IN_PAD_CONFIRMATION_PERIOD'


def test_create_pad_payment_request(session, client, jwt, app):
    """Assert payment request works for PAD accounts."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Create account first
    rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload(account_id=1234)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')
    # Update the payment account as ACTIVE
    activate_pad_account(auth_account_id)

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_no_contact_info(corp_type='BEN', filing_type_code='BCINC',
                                                 payment_method=PaymentMethod.PAD.value)),
                     headers=headers)
    assert rv.json.get('paymentMethod') == PaymentMethod.PAD.value
    assert not rv.json.get('isOnlineBankingAllowed')


def test_payment_request_online_banking_with_credit(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/accounts',
                     data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')

    # Update the payment account as ACTIVE
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    payment_account.credit = 51
    payment_account.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_payment_method(business_identifier='CP0002000', payment_method='ONLINE_BANKING')),
                     headers=headers)
    invoice_id = rv.json.get('id')

    rv = client.patch(f'/api/v1/payment-requests/{invoice_id}?applyCredit=true', data=json.dumps({}), headers=headers)

    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    assert payment_account.credit == 1

    # Now set the credit less than the total of invoice.
    payment_account.credit = 49
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/payment-requests', data=json.dumps(
        get_payment_request_with_payment_method(business_identifier='CP0002000', payment_method='ONLINE_BANKING')),
                     headers=headers)
    invoice_id = rv.json.get('id')

    rv = client.patch(f'/api/v1/payment-requests/{invoice_id}?applyCredit=true', data=json.dumps({}), headers=headers)
    # Credit won't be applied as the invoice total is 50 and the credit should remain as 0.
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    assert payment_account.credit == 0


def test_create_ejv_payment_request(session, client, jwt, app):
    """Assert payment request works for EJV accounts."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Create account first
    rv = client.post('/api/v1/accounts', data=json.dumps(get_gov_account_payload(account_id=1234)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')

    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    dist_code: DistributionCodeModel = DistributionCodeModel.find_by_active_for_account(payment_account.id)

    assert dist_code
    assert dist_code.account_id == payment_account.id

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    assert rv.json.get('paymentMethod') == PaymentMethod.EJV.value
    assert rv.json.get('statusCode') == InvoiceStatus.APPROVED.value


def test_payment_request_creation_for_wills(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    # Create account first
    rv = client.post('/api/v1/accounts', data=json.dumps(get_unlinked_pad_account_payload(account_id=1234)),
                     headers=headers)
    auth_account_id = rv.json.get('authAccountId')
    # Update the payment account as ACTIVE
    activate_pad_account(auth_account_id)

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
                     headers=headers)
    assert rv.json.get('serviceFees') == 1.5
    assert rv.json.get('total') == 28.5  # Wills Noticee : 17, Alias : 5 each for 2, service fee 1.5
    assert rv.json.get('lineItems')[0]['serviceFees'] == 1.5
    assert rv.json.get('lineItems')[1]['serviceFees'] == 0


def test_payment_request_creation_with_account_settings(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    system_token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    system_headers = {'Authorization': f'Bearer {system_token}', 'content-type': 'application/json'}
    # Create account first
    rv = client.post('/api/v1/accounts', data=json.dumps(get_gov_account_payload(account_id=1234)),
                     headers=system_headers)
    auth_account_id = rv.json.get('authAccountId')

    # Create account fee details.
    staff_token = jwt.create_jwt(get_claims(role=Role.STAFF_ADMIN.value), token_header)
    staff_headers = {'Authorization': f'Bearer {staff_token}', 'content-type': 'application/json'}
    client.post(f'/api/v1/accounts/{auth_account_id}/fees', data=json.dumps({'accountFees': [
        {
            'applyFilingFees': False,
            'serviceFeeCode': 'TRF02',  # 1.0
            'product': 'VS'  # Wills
        }
    ]}), headers=staff_headers)

    user_token = jwt.create_jwt(get_claims(), token_header)
    user_headers = {'Authorization': f'Bearer {user_token}', 'content-type': 'application/json',
                    'Account-Id': auth_account_id}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
                     headers=user_headers)
    assert rv.json.get('serviceFees') == 1.0
    assert rv.json.get('total') == 1.0  # Wills Noticee : 0, Alias : 0 each for 2, service fee 1.0
    assert rv.json.get('lineItems')[0]['serviceFees'] == 1.0
    assert rv.json.get('lineItems')[1]['serviceFees'] == 0

    # Now change the flag and try
    client.put(f'/api/v1/accounts/{auth_account_id}/fees/VS', data=json.dumps({
        'applyFilingFees': True,
        'serviceFeeCode': 'TRF02',  # 1.0
        'product': 'VS'  # Wills
    }), headers=staff_headers)

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
                     headers=user_headers)
    assert rv.json.get('serviceFees') == 1.0
    assert rv.json.get('total') == 28  # Wills Noticee : 17, Alias : 5 each for 2, service fee 1.0
    assert rv.json.get('lineItems')[0]['serviceFees'] == 1.0
    assert rv.json.get('lineItems')[1]['serviceFees'] == 0

    # Now change the serviceFeeCode
    client.put(f'/api/v1/accounts/{auth_account_id}/fees/VS', data=json.dumps({
        'applyFilingFees': True,
        'serviceFeeCode': 'TRF01',  # 1.0
        'product': 'VS'  # Wills
    }), headers=staff_headers)

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
                     headers=user_headers)
    assert rv.json.get('serviceFees') == 1.5
    assert rv.json.get('total') == 28.5  # Wills Noticee : 17, Alias : 5 each for 2, service fee 1.0
    assert rv.json.get('lineItems')[0]['serviceFees'] == 1.5
    assert rv.json.get('lineItems')[1]['serviceFees'] == 0
