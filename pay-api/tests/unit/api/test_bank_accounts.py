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

from pay_api.models.invoice import Invoice
from pay_api.models.payment_account import PaymentAccount
from pay_api.schemas import utils as schema_utils
from tests.utilities.base_test import (
    get_claims, get_payment_request, get_basic_account_payload, get_premium_account_payload, token_header)
from pay_api.utils.enums import Role


def test_bank_account_invalid_bank(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    valid_bank_details = {
        'bankNumber': '2001',
        'branchNumber': '00720  ',
        'accountNumber': '1234567',

    }

    rv = client.post('/api/v1/bank-accounts/verifications', data=json.dumps(valid_bank_details),
                     headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('message')[0] == 'Bank Number is Invalid'
    assert rv.json.get('isValid') is False
