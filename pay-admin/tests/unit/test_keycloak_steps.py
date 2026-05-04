# Copyright © 2026 Province of British Columbia
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
"""BDD step definitions for keycloak.feature."""

import flask
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from admin.keycloak import Keycloak
from tests.fake_oidc import FakeOidc

scenarios("features/keycloak.feature")


@pytest.fixture(autouse=True)
def reset_oidc():
    """Reset keycloak session."""
    Keycloak._oidc = FakeOidc()  # noqa: SLF001
    yield


@given("a user is logged in but has no access token")
def user_logged_in_no_token():
    """Logged in user with no token."""
    Keycloak._oidc.user_loggedin = True  # noqa: SLF001
    Keycloak._oidc.get_access_token = lambda: None  # noqa: SLF001


@when("we check if the user is logged in")
def check_is_logged_in(context):
    """Set is logged in."""
    context["result"] = Keycloak(None).is_logged_in()


@when(parsers.parse('we check if the user has access to "{required_role}"'))
def check_has_access(app, context, required_role):
    """Set roles."""
    roles = context.get("user_roles", [])
    with app.test_request_context():
        flask.session["oidc_auth_profile"] = {"roles": roles}
        context["result"] = Keycloak(None).has_access(required_role)


@when("we get the username")
def get_username(context):
    """Setup user name."""
    context["result"] = Keycloak(None).get_username()


@then("the result should be true")
def result_is_true(context):
    """Assert true."""
    assert context["result"] is True


@then("the result should be false")
def result_is_false(context):
    """Assert false."""
    assert context["result"] is False


@then(parsers.parse('the username should be "{expected}"'))
def username_should_be(context, expected):
    """Assert username."""
    assert context["result"] == expected
