"""Conf test.

Fixtures for testing.
"""
import pytest


@pytest.fixture(scope='function')
def clean_db():
    """Clean DB."""
    from flask_sqlalchemy import SQLAlchemy

    from admin import create_app
    from admin.keycloak import Keycloak
    from tests.fake_oidc import FakeOidc

    Keycloak._oidc = FakeOidc()
    app = create_app(run_mode='testing')

    db = SQLAlchemy(app)

    return db


@pytest.fixture(scope='function')
def db(clean_db):
    """DB."""
    yield clean_db
    clean_db.session.close()
