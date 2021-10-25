import os
import time

import pytest
from sqlalchemy import engine_from_config


@pytest.fixture(scope="function")
def clean_db():
    from flask_sqlalchemy import SQLAlchemy
    from admin import create_app

    from tests.fake_oidc import FakeOidc
    from admin.keycloak import Keycloak

    Keycloak._oidc = FakeOidc()
    app, admin = create_app(run_mode='testing')

    db = SQLAlchemy(app)

    return db


@pytest.fixture(scope="function")
def db(clean_db):
    yield clean_db
    clean_db.session.close()
