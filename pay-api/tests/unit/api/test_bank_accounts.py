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

from tests.utilities.base_test import (
    get_claims, token_header)


def test_bank_account_valid_bank(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    valid_bank_details = {
        'bankInstitutionNumber': '2001',
        'bankTransitNumber': '00720',
        'bankAccountNumber': '1234567',

    }

    rv = client.post('/api/v1/bank-accounts/verifications', data=json.dumps(valid_bank_details),
                     headers=headers)
    assert rv.status_code == 200
    print(rv.json)
