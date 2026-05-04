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
"""BDD step definitions for secured_view.feature."""

import flask
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from werkzeug.wrappers import Response

from admin.keycloak import Keycloak
from admin.views.distribution_code import DistributionCodeConfig
from pay_api.models import DistributionCode, db
from tests.fake_oidc import FakeOidc

scenarios("features/secured_view.feature")


@pytest.fixture(autouse=True)
def _app_ctx(app):
    with app.app_context():
        yield


@pytest.fixture(autouse=True)
def reset_oidc():
    """Reset oidc session."""
    Keycloak._oidc = FakeOidc()  # noqa: SLF001
    yield


@pytest.fixture(autouse=True)
def mock_redirect(monkeypatch):
    """Mock redirect for login."""
    monkeypatch.setattr(
        "admin.keycloak.Keycloak.get_redirect_url",
        lambda self: Response("redirect", status=302),  # noqa: ARG005
    )


@given("the SecuredView is loaded")
def load_secured_view(context):
    """Load the view."""
    context["view"] = DistributionCodeConfig(DistributionCode, db.session, endpoint="test_sv")


@given("the view has already redirected once")
def view_already_redirected(context):
    """Load connected state."""
    context["view"].connected = True


@given(parsers.parse('a user is logged in with roles "{role1}" and "{role2}"'))
def user_logged_in_with_two_roles(role1, role2, context):
    """Set two roles on the fake OIDC session."""
    Keycloak._oidc.user_loggedin = True  # noqa: SLF001
    context["user_roles"] = [role1, role2]


@when("we check create and edit permissions")
def check_create_edit_permissions(app, context):
    """Evaluate can_create and can_edit inside a request context with the user's roles."""
    roles = context.get("user_roles", [])
    with app.test_request_context():
        flask.session["oidc_auth_profile"] = {"roles": roles}
        context["can_create"] = context["view"].can_create
        context["can_edit"] = context["view"].can_edit


@when("the inaccessible view is requested")
def inaccessible_requested(context):
    """Set a request which is not accessible."""
    context["response"] = context["view"].inaccessible_callback("test")


@then("deletion should not be allowed")
def cannot_delete(context):
    """Assert delete is not allowed."""
    assert context["view"].can_delete is False


@then("create should be allowed")
def create_allowed(context):
    """Assert can_create is True."""
    assert context["can_create"] is True


@then("create should not be allowed")
def create_not_allowed(context):
    """Assert can_create is False."""
    assert context["can_create"] is False


@then("edit should be allowed")
def edit_allowed(context):
    """Assert can_edit is True."""
    assert context["can_edit"] is True


@then("edit should not be allowed")
def edit_not_allowed(context):
    """Assert can_edit is False."""
    assert context["can_edit"] is False


@then("the response should be a redirect to login")
def response_is_redirect(context):
    """Assert redirect is triggered."""
    assert isinstance(context["response"], Response)
    assert context["response"].status_code == 302


@then(parsers.parse('the response should be "{expected}"'))
def response_is(context, expected):
    """Assert response."""
    assert context["response"] == expected
