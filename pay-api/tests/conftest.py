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

from concurrent.futures import CancelledError
import pytest
from flask_migrate import Migrate, upgrade
from sqlalchemy import event, text
from sqlalchemy.schema import DropConstraint, MetaData

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
                """Result mock."""
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


@pytest.fixture(scope='session')
def db(app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a session-wide initialised database.

    Drops all existing tables - Meta follows Postgres FKs
    """
    with app.app_context():
        # Clear out views
        view_sql = """SELECT table_name FROM information_schema.views
                WHERE table_schema='public'
            """

        sess = _db.session()
        for seq in [name for (name,) in sess.execute(text(view_sql))]:
            try:
                sess.execute(text('DROP VIEW public.%s ;' % seq))
                print('DROP VIEW public.%s ' % seq)
            except Exception as err:  # NOQA pylint: disable=broad-except
                print(f'Error: {err}')
        sess.commit()

        # Clear out any existing tables
        metadata = MetaData(_db.engine)
        metadata.reflect()
        for table in metadata.tables.values():
            for fk in table.foreign_keys:  # pylint: disable=invalid-name
                _db.engine.execute(DropConstraint(fk.constraint))
        metadata.drop_all()
        _db.drop_all()

        sequence_sql = """SELECT sequence_name FROM information_schema.sequences
                          WHERE sequence_schema='public'
                       """

        sess = _db.session()
        for seq in [name for (name,) in sess.execute(text(sequence_sql))]:
            try:
                sess.execute(text('DROP SEQUENCE public.%s ;' % seq))
                print('DROP SEQUENCE public.%s ' % seq)
            except Exception as err:  # NOQA pylint: disable=broad-except
                print(f'Error: {err}')
        sess.commit()

        # ############################################
        # There are 2 approaches, an empty database, or the same one that the app will use
        #     create the tables
        #     _db.create_all()
        # or
        # Use Alembic to load all of the DB revisions including supporting lookup data
        # This is the path we'll use in legal_api!!

        # even though this isn't referenced directly, it sets up the internal configs that upgrade needs
        Migrate(app, _db)
        upgrade()

        return _db


@pytest.fixture(scope='function', autouse=True)
def session(app, db):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a function-scoped session."""
    with app.app_context():
        conn = db.engine.connect()
        txn = conn.begin()

        options = dict(bind=conn, binds={})
        sess = db.create_scoped_session(options=options)

        # establish  a SAVEPOINT just before beginning the test
        # (http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#using-savepoint)
        sess.begin_nested()

        @event.listens_for(sess(), 'after_transaction_end')
        def restart_savepoint(sess2, trans):  # pylint: disable=unused-variable
            # Detecting whether this is indeed the nested transaction of the test
            if trans.nested and not trans._parent.nested:  # pylint: disable=protected-access
                # Handle where test DOESN'T session.commit(),
                sess2.expire_all()
                sess.begin_nested()

        db.session = sess

        sql = text('select 1')
        sess.execute(sql)

        yield sess

        # Cleanup
        sess.remove()
        # This instruction rollsback any commit that were executed in the tests.
        txn.rollback()
        conn.close()


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
    import os
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


@pytest.fixture()
def non_active_accounts_auth_api_mock(monkeypatch):
    """Mock auth rest call to get non-active orgs."""
    def _get_non_active_orgs():
        return ['911']
    monkeypatch.setattr('pay_api.services.payment_account.PaymentAccount._get_non_active_org_ids',
                        _get_non_active_orgs)
