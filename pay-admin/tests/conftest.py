"""Conf test.

Fixtures for testing.
"""

import pytest
from flask_sqlalchemy import SQLAlchemy

from admin import create_app
from admin.keycloak import Keycloak
from tests.fake_oidc import FakeOidc


@pytest.fixture(scope="function")
def db():
    """DB."""
    Keycloak._oidc = FakeOidc()  # pylint-disable=protected-access
    app = create_app(run_mode="testing")
    with app.app_context():
        _db = SQLAlchemy()
        _db.app = app
        return _db
