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

"""Tests to assure the BCOL service layer.

Test-Suite to ensure that the BCOL Service layer is working as expected.
"""

from bcol_api.services.bcol_profile import BcolProfile


def test_query_profile(app, ldap_mock, query_profile_mock):
    """Test query profile service."""
    with app.app_context():
        query_profile_response = BcolProfile().query_profile("TEST", "TEST")
        assert query_profile_response.get("userId") == "PB25020"
        assert query_profile_response.get("address").get("country") == "CA"


def test_standardize_country():
    """Test standardize country to code."""
    code = BcolProfile().standardize_country("CANADA")
    assert code == "CA"

    code = BcolProfile().standardize_country("CA")
    assert code == "CA"

    code = BcolProfile().standardize_country("Test")
    assert code == "Test"
