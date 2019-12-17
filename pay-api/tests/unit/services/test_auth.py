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
from pay_api.utils.constants import EDIT_ROLE, VIEW_ROLE
from pay_api.utils.enums import Role
from tests.utilities.base_test import get_claims, token_header


def test_auth_role_for_service_account(app, jwt, monkeypatch):
    """Assert the auth works for service account."""
    def mock_auth(fake1, fake2):  # pylint: disable=unused-argument; mocks of library methods
        token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value, Role.EDITOR.value]), token_header)
        headers = {'Authorization': 'Bearer ' + token}
        return headers['Authorization']

    with app.test_request_context():
        monkeypatch.setattr('flask.request.headers.get', mock_auth)
        # Test one of roles
        check_auth('CP0001234', jwt=jwt, one_of_roles=[EDIT_ROLE])


def test_auth_role_for_service_account_with_no_edit_role(app, jwt, monkeypatch):
    """Assert the auth works for service account."""
    def mock_auth(fake1, fake2):  # pylint: disable=unused-argument; mocks of library methods
        token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value], role=''), token_header)
        headers = {'Authorization': 'Bearer ' + token}
        return headers['Authorization']

    with app.test_request_context():
        monkeypatch.setattr('flask.request.headers.get', mock_auth)
        with pytest.raises(HTTPException) as excinfo:
            # Test one of roles
            check_auth('CP0001234', jwt=jwt, one_of_roles=[EDIT_ROLE])
            assert excinfo.exception.code == 403


def test_auth_for_client_user_roles(app, jwt, monkeypatch):
    """Assert that the auth is working as expected."""
    token = jwt.create_jwt(get_claims(roles=[Role.EDITOR.value]), token_header)

    headers = {'Authorization': 'Bearer ' + token}

    def mock_auth(one, two):  # pylint: disable=unused-argument; mocks of library methods
        return headers['Authorization']

    with app.test_request_context():
        monkeypatch.setattr('flask.request.headers.get', mock_auth)

        # Test one of roles
        check_auth('CP0001234', jwt=jwt, one_of_roles=[EDIT_ROLE])
        # Test contains roles
        check_auth('CP0001234', jwt=jwt, contains_role=EDIT_ROLE)

        # Test for exception
        with pytest.raises(HTTPException) as excinfo:
            check_auth('CP0000000', jwt=jwt, contains_role=VIEW_ROLE)
            assert excinfo.exception.code == 403

        with pytest.raises(HTTPException) as excinfo:
            check_auth('CP0000000', jwt=jwt, one_of_roles=[EDIT_ROLE])
            assert excinfo.exception.code == 403
