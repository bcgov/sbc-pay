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

"""Common setup and fixtures for the py-test suite used by this service."""

import os
import time
from unittest.mock import Mock

import pytest
from flask_migrate import Migrate, upgrade
from pay_api.models import db as _db
from sqlalchemy import event, text
from sqlalchemy_utils import create_database, database_exists, drop_database

from invoke_jobs import create_app
from utils.logger import setup_logging


@pytest.fixture(autouse=True)
def mock_pub_sub_call(mocker):
    """Mock pub sub call."""

    class Expando(object):
        """Expando class."""

    class PublisherMock:
        """Publisher Mock."""

        def __init__(self, *args, **kwargs):
            def result():
                """Return true for mock."""
                return True

            self.result = result

        def publish(self, *args, **kwargs):
            """Publish mock."""
            ex = Expando()
            ex.result = self.result
            return ex

    mocker.patch("google.cloud.pubsub_v1.PublisherClient", PublisherMock)


@pytest.fixture(scope="session")
def app():
    """Return a session-wide application configured in TEST mode."""
    return create_app("testing")


@pytest.fixture(scope="function")
def app_request():
    """Return a session-wide application configured in TEST mode."""
    return create_app("testing")


@pytest.fixture(scope="session")
def client(app):  # pylint: disable=redefined-outer-name
    """Return a session-wide Flask test client."""
    return app.test_client()


@pytest.fixture(scope="session")
def client_ctx(app):
    """Return session-wide Flask test client."""
    with app.test_client() as _client:
        yield _client


@pytest.fixture(scope="session", autouse=True)
def db(app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a session-wide initialised database."""
    with app.app_context():
        if database_exists(_db.engine.url):
            drop_database(_db.engine.url)
        create_database(_db.engine.url)
        _db.session().execute(text('SET TIME ZONE "UTC";'))
        pay_api_dir = os.path.abspath("..").replace("jobs", "pay-api")
        pay_api_dir = os.path.join(pay_api_dir, "migrations")
        Migrate(app, _db, directory=pay_api_dir)
        upgrade()
        # Restore the logging, alembic and sqlalchemy have their own logging from alembic.ini.
        setup_logging(os.path.abspath("logging.conf"))
        return _db


@pytest.fixture(scope="function", autouse=True)
def session(db, app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a function-scoped session."""
    with app.app_context():
        with db.engine.connect() as conn:
            transaction = conn.begin()
            sess = db._make_scoped_session(dict(bind=conn))  # pylint: disable=protected-access
            # Establish SAVEPOINT (http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#using-savepoint)
            nested = sess.begin_nested()
            db.session = sess
            db.session.commit = nested.commit
            db.session.rollback = nested.rollback

            @event.listens_for(sess, "after_transaction_end")
            def restart_savepoint(sess2, trans):  # pylint: disable=unused-variable
                nonlocal nested
                if trans.nested:
                    # Handle where test DOESN'T session.commit()
                    sess2.expire_all()
                    nested = sess.begin_nested()
                    # When using a SAVEPOINT via the Session.begin_nested() or Connection.begin_nested() methods,
                    # the transaction object returned must be used to commit or rollback the SAVEPOINT.
                    # Calling the Session.commit() or Connection.commit() methods will always commit the
                    # outermost transaction; this is a SQLAlchemy 2.0 specific behavior that is
                    # reversed from the 1.x series
                    db.session = sess
                    db.session.commit = nested.commit
                    db.session.rollback = nested.rollback

            try:
                yield db.session
            finally:
                db.session.remove()
                transaction.rollback()


@pytest.fixture(scope="session", autouse=True)
def auto(docker_services, app):
    """Spin up docker instances."""
    if app.config["USE_DOCKER_MOCK"]:
        docker_services.start("keycloak")
        docker_services.wait_for_service("keycloak", 8081)
        docker_services.start("bcol")
        docker_services.start("auth")
        docker_services.start("paybc")
        docker_services.start("reports")
        docker_services.start("proxy")
        docker_services.start("sftp")
        time.sleep(2)


@pytest.fixture(scope="session")
def docker_compose_files(pytestconfig):
    """Get the docker-compose.yml absolute path."""
    return [os.path.join(str(pytestconfig.rootdir), "tests/docker", "docker-compose.yml")]


@pytest.fixture()
def admin_users_mock(monkeypatch):
    """Mock auth rest call to get org admins."""

    def get_account_admin_users(payment_account, **kwargs):
        return {
            "members": [
                {
                    "id": 4048,
                    "membershipStatus": "ACTIVE",
                    "membershipTypeCode": "ADMIN",
                    "user": {
                        "contacts": [
                            {
                                "email": "test@test.com",
                                "phone": "(250) 111-2222",
                                "phoneExtension": "",
                            }
                        ],
                        "firstname": "FIRST",
                        "id": 18,
                        "lastname": "LAST",
                        "loginSource": "BCSC",
                    },
                }
            ]
        }

    monkeypatch.setattr("pay_api.services.auth.get_account_admin_users", get_account_admin_users)


@pytest.fixture()
def google_bucket_mock(monkeypatch):
    """Mock google bucket upload."""

    def upload_to_bucket(p1, p2):
        return None

    monkeypatch.setattr("tasks.common.cgi_ejv.upload_to_bucket", upload_to_bucket)


@pytest.fixture()
def emails_with_keycloak_role_mock(monkeypatch):
    """Mock auth rest call to get org admins."""

    def get_emails_with_keycloak_role(role):
        return "test@email.com"

    monkeypatch.setattr(
        "tasks.eft_overpayment_notification_task.get_emails_with_keycloak_role",
        get_emails_with_keycloak_role,
    )


@pytest.fixture()
def send_email_mock(monkeypatch):
    """Mock send_email."""
    send_email = Mock(return_value=True)
    monkeypatch.setattr("tasks.eft_overpayment_notification_task.send_email", send_email)
    return send_email
