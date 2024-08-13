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

"""Common setup and fixtures for the py-test suite used by this service."""

import os

import pytest
from flask_migrate import Migrate, upgrade
from sqlalchemy import event, text
from sqlalchemy_utils import create_database, database_exists, drop_database

from pay_api import create_app
from pay_api import jwt as _jwt
from pay_api import setup_jwt_manager
from pay_api.models import db as _db


@pytest.fixture(scope='session', autouse=True)
def app():
    """Return a session-wide application configured in TEST mode."""
    _app = create_app('testing')
    return _app


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

    mocker.patch('google.cloud.pubsub_v1.PublisherClient', PublisherMock)


@pytest.fixture(scope='function')
def app_request():
    """Return a session-wide application configured in TEST mode."""
    _app = create_app('testing')
    return _app


@pytest.fixture(scope='session')
def client(app):  # pylint: disable=redefined-outer-name
    """Return a session-wide Flask test client."""
    return app.test_client()


@pytest.fixture(scope='session')
def jwt(app):
    """Return session-wide jwt manager."""
    return _jwt


@pytest.fixture(scope='session')
def client_ctx(app):
    """Return session-wide Flask test client."""
    with app.test_client() as _client:
        yield _client


@pytest.fixture(scope='session', autouse=True)
def db(app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a session-wide initialised database."""
    with app.app_context():
        if database_exists(_db.engine.url):
            drop_database(_db.engine.url)
        create_database(_db.engine.url)
        _db.session().execute(text('SET TIME ZONE "UTC";'))
        Migrate(app, _db)
        upgrade()
        return _db


@pytest.fixture(scope='function')
def session(db, app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a function-scoped session."""
    with app.app_context():
        with db.engine.connect() as conn:
            transaction = conn.begin()
            sess = db._make_scoped_session(dict(bind=conn))  # pylint: disable=protected-access
            # Establish SAVEPOINT (http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#using-savepoint)
            nested = sess.begin_nested()
            old_session = db.session
            db.session = sess
            db.session.commit = nested.commit
            db.session.rollback = nested.rollback

            @event.listens_for(sess, 'after_transaction_end')
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
                event.remove(sess, 'after_transaction_end', restart_savepoint)
                db.session = old_session


@pytest.fixture()
def auth_mock(monkeypatch):
    """Mock check_auth."""
    monkeypatch.setattr('pay_api.services.auth.check_auth', lambda *args, **kwargs: None)


@pytest.fixture()
def public_user_mock(monkeypatch):
    """Mock user_context."""
    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            'username': 'public user',
            'realm_access': {
                'roles': [
                    'public_user',
                    'edit'
                ]
            }
        }

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return 'test'

    monkeypatch.setattr('pay_api.utils.user_context._get_token', mock_auth)
    monkeypatch.setattr('pay_api.utils.user_context._get_token_info', token_info)


@pytest.fixture()
def staff_user_mock(monkeypatch):
    """Mock user_context."""
    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            'username': 'staff user',
            'realm_access': {
                'roles': [
                    'staff',
                    'edit'
                ]
            }
        }

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return 'test'

    monkeypatch.setattr('pay_api.utils.user_context._get_token', mock_auth)
    monkeypatch.setattr('pay_api.utils.user_context._get_token_info', token_info)


@pytest.fixture()
def system_user_mock(monkeypatch):
    """Mock user_context."""
    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            'username': 'system user',
            'realm_access': {
                'roles': [
                    'system',
                    'edit'
                ]
            }
        }

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return 'test'

    monkeypatch.setattr('pay_api.utils.user_context._get_token', mock_auth)
    monkeypatch.setattr('pay_api.utils.user_context._get_token_info', token_info)


@pytest.fixture(scope='session', autouse=True)
def auto(docker_services, app):
    """Spin up a keycloak instance and initialize jwt."""
    if app.config['USE_TEST_KEYCLOAK_DOCKER']:
        docker_services.start('keycloak')
        docker_services.wait_for_service('keycloak', 8081)

    setup_jwt_manager(app, _jwt)
    if app.config['USE_DOCKER_MOCK']:
        docker_services.start('bcol')
        docker_services.start('auth')
        docker_services.start('paybc')
        docker_services.start('reports')
        docker_services.start('proxy')


@pytest.fixture(scope='session')
def docker_compose_files(pytestconfig):
    """Get the docker-compose.yml absolute path."""
    return [
        os.path.join(str(pytestconfig.rootdir), 'tests/docker', 'docker-compose.yml')
    ]


@pytest.fixture()
def premium_user_mock(monkeypatch):
    """Mock auth."""
    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            {
                'orgMembership': 'OWNER',
                'roles': ['view', 'edit'],
                'business': {
                    'folioNumber': 'MOCK1234',
                    'name': 'Mock Business'
                },
                'account': {
                    'accountType': 'PREMIUM',
                    'paymentPreference': {
                        'methodOfPayment': 'DRAWDOWN',
                        'bcOnlineUserId': 'PB25020',
                        'bcOnlineAccountId': ''
                    },
                    'id': '1234',
                    'name': 'Mock Account'
                },
                'corp_type_code': ''
            }
        }

    def account_id():
        return '1'

    monkeypatch.setattr('pay_api.services.auth.check_auth', token_info)
    monkeypatch.setattr('pay_api.utils.user_context.get_auth_account_id', account_id)


@pytest.fixture()
def rest_call_mock(monkeypatch):
    """Mock rest_call_mock."""
    monkeypatch.setattr('pay_api.services.oauth_service.OAuthService.post', lambda *args, **kwargs: None)


@pytest.fixture()
def admin_users_mock(monkeypatch):
    """Mock auth rest call to get org admins."""
    def _get_account_admin_users(payment_account):
        return {
            'members': [
                {
                    'id': 4048,
                    'membershipStatus': 'ACTIVE',
                    'membershipTypeCode': 'ADMIN',
                    'user': {
                        'contacts': [
                            {
                                'email': 'test@test.com',
                                'phone': '(250) 111-2222',
                                'phoneExtension': ''
                            }
                        ],
                        'firstname': 'FIRST',
                        'id': 18,
                        'lastname': 'LAST',
                        'loginSource': 'BCSC'
                    }
                }
            ]
        }
    monkeypatch.setattr('pay_api.services.payment_account.PaymentAccount._get_account_admin_users',
                        _get_account_admin_users)
