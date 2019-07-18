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

"""Tests to assure the bcol accounts end-point.

Test-Suite to ensure that the /accounts/<id>/users/<user_id> endpoint is working as expected.
"""
from datetime import date, timedelta

from pay_api.models import CorpType, FeeCode, FeeSchedule, FilingType
from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import Role


def test_get_account_profile(session, client, jwt, app):
    """Assert that the endpoint returns 200."""

    rv = client.get(f'/api/v1/bcol/accounts/123456789/users/123456', headers={})
    assert rv.status_code == 400
