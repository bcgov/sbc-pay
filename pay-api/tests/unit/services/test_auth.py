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

"""Tests to assure the auth Service.

Test-Suite to ensure that the auth Service is working as expected.
"""

import pytest
from werkzeug.exceptions import HTTPException

from pay_api.services.auth import check_auth
from pay_api.utils.constants import OWNER_ROLE, STAFF_ROLE


def test_auth_for_roles(session):
    """Assert that the auth is working as expected."""
    # Test one of roles
    check_auth('CP0001234', None, one_of_roles=[OWNER_ROLE])
    # Test disabled roles
    check_auth('CP0001234', None, disabled_roles=[STAFF_ROLE])
    # Test contains roles
    check_auth('CP0001234', None, contains_role=OWNER_ROLE)

    # Test for exception
    with pytest.raises(HTTPException) as excinfo:
        check_auth('CP0001234', None, contains_role=STAFF_ROLE)
        assert excinfo.exception.code == 403

    with pytest.raises(HTTPException) as excinfo:
        check_auth('CP0001234', None, one_of_roles=[STAFF_ROLE])
        assert excinfo.exception.code == 403

    with pytest.raises(HTTPException) as excinfo:
        check_auth('CP0001234', None, contains_role=STAFF_ROLE)
        assert excinfo.exception.code == 403
