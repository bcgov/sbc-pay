"""Common fixtures and shared @given steps for the pay-admin test suite.

See tests/README.md for an overview of how the BDD tests work.
"""

import pytest
from pytest_bdd import given, parsers

from admin import create_app
from admin.keycloak import Keycloak
from tests.fake_oidc import FakeOidc


@pytest.fixture(scope="session")
def app():
    """Session-wide Flask app with a long-lived app context."""
    Keycloak._oidc = FakeOidc()  # noqa: SLF001
    flask_app = create_app(run_mode="testing")
    ctx = flask_app.app_context()
    ctx.push()
    yield flask_app
    ctx.pop()


@pytest.fixture(scope="session")
def client(app):
    """Session-wide Flask test client."""
    return app.test_client()


@pytest.fixture
def context():
    """Fresh dict shared between Given - When → Then steps."""
    return {}


@given("a user is logged in")
def user_is_logged_in():
    """Set user as logged in."""
    Keycloak._oidc.user_loggedin = True  # noqa: SLF001


@given("a user is not logged in")
def user_is_not_logged_in():
    """Set user as not logged in."""
    Keycloak._oidc.user_loggedin = False  # noqa: SLF001


@given(parsers.parse('a user is logged in as "{username}"'))
def user_is_logged_in_as(username):
    """Set user as logged in with username."""
    Keycloak._oidc.user_loggedin = True  # noqa: SLF001
    Keycloak._oidc.user_getfield = lambda key: username  # noqa: SLF001,ARG005


@given(parsers.parse('a user is logged in with role "{role}"'))
def user_is_logged_in_with_role(role, context):
    """Set user as logged in with a role."""
    Keycloak._oidc.user_loggedin = True  # noqa: SLF001
    context["user_roles"] = [role]


@given(parsers.parse('the current time is "{timestamp}"'))
def the_current_time_is(timestamp, context):
    """Set timestamp."""
    context["timestamp"] = timestamp
