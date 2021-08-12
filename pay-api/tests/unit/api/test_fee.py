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

"""Tests to assure the fees end-point.

Test-Suite to ensure that the /fees endpoint is working as expected.
"""
import json
from datetime import date, timedelta

from pay_api.models import CorpType, FeeCode, FeeSchedule, FilingType
from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import Role
from tests.utilities.base_test import get_claims, get_gov_account_payload, token_header


def test_fees_with_corp_type_and_filing_type(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]


def test_fees_with_corp_type_and_filing_type_with_valid_start_date(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    now = date.today()
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100),
        now - timedelta(1))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?valid_date={now}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    assert not schema_utils.validate(rv.json, 'problem')[0]


def test_fees_with_corp_type_and_filing_type_with_invalid_start_date(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    now = date.today()
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100),
        now + timedelta(1))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?valid_date={now}', headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, 'problem')[0]
    assert not schema_utils.validate(rv.json, 'fees')[0]


def test_fees_with_corp_type_and_filing_type_with_valid_end_date(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    now = date.today()
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100),
        now - timedelta(1),
        now)
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?valid_date={now}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]


def test_fees_with_corp_type_and_filing_type_with_invalid_end_date(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    # Insert a record first and then query for it
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    now = date.today()
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100),
        now - timedelta(2),
        now - timedelta(1))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?valid_date={now}', headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, 'problem')[0]


def test_calculate_fees_with_waive_fees(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role='staff'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?waiveFees=true', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    assert rv.json.get('filingFees') == 0


def test_calculate_fees_with_waive_fees_unauthorized(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?waiveFees=true', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    assert rv.json.get('filingFees') == 100


def test_fees_with_quantity(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}?quantity=10', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]


def test_calculate_fees_for_service_fee(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'
    service_fee = factory_fee_model('SF01', 1.5)
    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 100),
        service_fee=service_fee)

    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    assert rv.json.get('filingFees') == 100
    assert rv.json.get('serviceFees') == 1.5


def test_calculate_fees_with_zero_service_fee(session, client, jwt, app):
    """Assert that service fee is zero if the filing fee is zero."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    corp_type = 'XX'
    filing_type_code = 'XOTANN'

    factory_fee_schedule_model(
        factory_filing_type_model('XOTANN', 'TEST'),
        factory_corp_type_model('XX', 'TEST'),
        factory_fee_model('XXX', 0))
    rv = client.get(f'/api/v1/fees/{corp_type}/{filing_type_code}', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    assert rv.json.get('filingFees') == 0
    assert rv.json.get('serviceFees') == 0


def test_fee_for_account_fee_settings(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post('/api/v1/accounts', data=json.dumps(get_gov_account_payload()),
                     headers=headers)

    account_id = rv.json.get('accountId')

    # Create account fee details.
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_ACCOUNTS.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    client.post(f'/api/v1/accounts/{account_id}/fees', data=json.dumps({'accountFees': [
        {
            'applyFilingFees': False,
            'serviceFeeCode': 'TRF02',  # 1.0
            'product': 'BUSINESS'
        }
    ]}), headers=headers)

    # Get fee for this account.
    token = jwt.create_jwt(get_claims(role=Role.EDITOR.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': account_id}
    rv = client.get('/api/v1/fees/BEN/BCANN', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    # assert filing fee is not applied and service fee is applied
    assert rv.json.get('filingFees') == 0
    assert rv.json.get('serviceFees') == 1.0

    # Now change the settings to apply filing fees and assert
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_ACCOUNTS.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    client.put(f'/api/v1/accounts/{account_id}/fees/BUSINESS', data=json.dumps({
        'applyFilingFees': True,
        'serviceFeeCode': 'TRF01',  # 1.5
        'product': 'BUSINESS'
    }), headers=headers)

    # Get fee for this account.
    token = jwt.create_jwt(get_claims(role=Role.EDITOR.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json', 'Account-Id': account_id}
    rv = client.get('/api/v1/fees/BEN/BCANN', headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, 'fees')[0]
    # assert filing fee is applied and service fee is applied
    assert rv.json.get('filingFees') > 0
    assert rv.json.get('serviceFees') == 1.5


def factory_filing_type_model(
        filing_type_code: str,
        filing_description: str = 'TEST'):
    """Return the filing type model."""
    filing_type = FilingType(code=filing_type_code,
                             description=filing_description)
    filing_type.save()
    return filing_type


def factory_fee_model(
        fee_code: str,
        amount: int):
    """Return the fee code model."""
    fee_code_master = FeeCode(code=fee_code,
                              amount=amount)
    fee_code_master.save()
    return fee_code_master


def factory_corp_type_model(
        corp_type_code: str,
        corp_type_description: str):
    """Return the corp type model."""
    corp_type = CorpType(code=corp_type_code,
                         description=corp_type_description)
    corp_type.save()
    return corp_type


def factory_fee_schedule_model(
        filing_type: FilingType,
        corp_type: CorpType,
        fee_code: FeeCode,
        fee_start_date: date = date.today(),
        fee_end_date: date = None,
        service_fee: FeeCode = None):
    """Return the fee schedule model."""
    fee_schedule = FeeSchedule(filing_type_code=filing_type.code,
                               corp_type_code=corp_type.code,
                               fee_code=fee_code.code,
                               fee_start_date=fee_start_date,
                               fee_end_date=fee_end_date
                               )
    if service_fee:
        fee_schedule.service_fee_code = service_fee.code
    fee_schedule.save()
    return fee_schedule
