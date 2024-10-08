# Copyright © 2024 Province of British Columbia
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

"""Tests to assure the fees/schedules end-point.

Test-Suite to ensure that the /fees/schedules endpoint is working as expected.
"""

from tests.utilities.base_test import get_claims, token_header


def test_get_fees_schedules(client, jwt):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role="staff"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get("/api/v1/fees/schedules", headers=headers)
    assert rv.status_code == 200


def test_get_schedule_with_description(client, jwt):
    """Assert that the search works."""
    token = jwt.create_jwt(get_claims(role="staff"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    search = "NSF"
    rv = client.get(f"/api/v1/fees/schedules?description={search}", headers=headers)
    assert rv.status_code == 200
    assert len(rv.json.get("items")) == 1
    assert rv.json.get("items")[0].get("corpTypeCode").get("code") == "BCR"
    assert rv.json.get("items")[0].get("filingTypeCode").get("description") == search

    search = "Community Contribution Company"
    rv = client.get(f"/api/v1/fees/schedules?description={search}", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("items")[0].get("corpTypeCode").get("code") == "CC"
    assert rv.json.get("items")[0].get("corpTypeCode").get("description") == search

    rv = client.get(
        f"/api/v1/fees/schedules?description={search[:-5]}", headers=headers
    )
    assert rv.status_code == 200
    assert rv.json.get("items")[0].get("corpTypeCode").get("code") == "CC"
    assert rv.json.get("items")[0].get("corpTypeCode").get("description") == search
