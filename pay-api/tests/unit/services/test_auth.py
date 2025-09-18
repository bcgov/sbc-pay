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

"""Tests to assure the auth Service.

Test-Suite to ensure that the auth Service is working as expected.
"""

from unittest.mock import patch

import pytest
from werkzeug.exceptions import HTTPException

from pay_api.services.auth import check_auth
from pay_api.utils.constants import EDIT_ROLE, VIEW_ROLE
from pay_api.utils.user_context import get_original_user_sub, get_original_username


def test_auth_role_for_service_account(session, monkeypatch):
    """Assert the auth works for service account."""

    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            "username": "service account",
            "realm_access": {"roles": ["system", "edit"]},
            "product_code": "BUSINESS",
        }

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return "test"

    monkeypatch.setattr("pay_api.utils.user_context._get_token", mock_auth)
    monkeypatch.setattr("pay_api.utils.user_context._get_token_info", token_info)

    # Test one of roles
    check_auth("CP0001234", one_of_roles=[EDIT_ROLE])


def test_auth_role_for_service_account_with_no_edit_role(session, monkeypatch):
    """Assert the auth works for service account."""

    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {"username": "service account", "realm_access": {"roles": ["system"]}}

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return "test"

    monkeypatch.setattr("pay_api.utils.user_context._get_token", mock_auth)
    monkeypatch.setattr("pay_api.utils.user_context._get_token_info", token_info)

    with pytest.raises(HTTPException) as excinfo:
        # Test one of roles
        check_auth("CP0001234", one_of_roles=[EDIT_ROLE])
        assert excinfo.exception.code == 403


def test_auth_for_client_user_roles(session, public_user_mock):
    """Assert that the auth is working as expected."""
    # Test one of roles
    check_auth("CP0001234", one_of_roles=[EDIT_ROLE])
    # Test contains roles
    check_auth("CP0001234", contains_role=EDIT_ROLE)


@pytest.mark.parametrize("roles, param_name", [(VIEW_ROLE, "contains_role"), ([EDIT_ROLE], "one_of_roles")])
def test_auth_for_client_user_roles_for_error(session, public_user_mock, roles, param_name):
    """Assert that the auth is working as expected."""
    # Test for exception
    with pytest.raises(HTTPException) as excinfo:
        check_auth("CP0000000", param_name=roles)
        assert excinfo.exception.code == 403


@pytest.mark.parametrize(
    "function,header,input_value,expected",
    [
        (get_original_user_sub, "Original-Sub", "123-abc!@#$%^&*()_+{}|:<>?[];'\",./", "123-abc"),
        (
            get_original_username,
            "Original-Username",
            "user@domain\\test!@#$%^&*()_+{}|:<>?[];'\",./",
            "user@domain\\test@_",
        ),
        (get_original_user_sub, "Original-Sub", "", None),
        (get_original_username, "Original-Username", "", None),
        (get_original_user_sub, "Original-Sub", "!@#$%^&*()_+{}|:<>?[];'\",./", None),
        (get_original_username, "Original-Username", "!@#$%^&*()_+{}|:<>?[];'\",./", "@_"),
    ],
)
def test_sanitization(function, header, input_value, expected):
    """Test sanitization for both functions with various inputs."""
    with patch("pay_api.utils.user_context.request") as mock_request:
        mock_request.headers = {header: input_value}
        result = function(is_system=True)
        assert result == expected


@pytest.mark.parametrize("function", [get_original_user_sub, get_original_username])
def test_non_system_user_returns_none(function):
    """Test both functions return None for non-system users."""
    result = function(is_system=False)
    assert result is None


@pytest.mark.parametrize(
    "function,header",
    [
        (get_original_user_sub, "Original-Sub"),
        (get_original_username, "Original-Username"),
    ],
)
def test_no_request_returns_none(function, header):
    """Test both functions return None when request is None."""
    with patch("pay_api.utils.user_context.request", None):
        result = function(is_system=True)
        assert result is None


@pytest.mark.parametrize(
    "function,header",
    [
        (get_original_user_sub, "Original-Sub"),
        (get_original_username, "Original-Username"),
    ],
)
def test_missing_header_returns_none(function, header):
    """Test both functions return None when header is missing."""
    with patch("pay_api.utils.user_context.request") as mock_request:
        mock_request.headers = {}
        result = function(is_system=True)
        assert result is None
