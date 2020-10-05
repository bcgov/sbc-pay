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

import asyncio
import os
import random
import time

import pytest
from flask_migrate import Migrate, upgrade
from nats.aio.client import Client as Nats
from sqlalchemy import event, text
from sqlalchemy.schema import DropConstraint, MetaData
from stan.aio.client import Client as Stan

from pay_api import create_app, setup_jwt_manager
from pay_api import jwt as _jwt
from pay_api.models import db as _db


@pytest.fixture(scope='session')
def app():
    """Return a session-wide application configured in TEST mode."""
    _app = create_app('testing')

    return _app


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
            except Exception as err:  # pylint: disable=broad-except
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


@pytest.fixture(scope='function')
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


@pytest.fixture(scope='function')
def client_id():
    """Return a unique client_id that can be used in tests."""
    _id = random.SystemRandom().getrandbits(0x58)
    #     _id = (base64.urlsafe_b64encode(uuid.uuid4().bytes)).replace('=', '')

    return f'client-{_id}'


@pytest.fixture(scope='session')
def stan_server(docker_services):
    """Create the nats / stan services that the integration tests will use."""
    if os.getenv('TEST_NATS_DOCKER'):
        docker_services.start('nats')
        time.sleep(2)


@pytest.fixture(scope='function')
@pytest.mark.asyncio
async def stan(event_loop, client_id):
    """Create a stan connection for each function, to be used in the tests."""
    nc = Nats()
    sc = Stan()
    cluster_name = 'test-cluster'

    await nc.connect(io_loop=event_loop, name='entity.filing.tester')

    await sc.connect(cluster_name, client_id, nats=nc)

    yield sc

    await sc.close()
    await nc.close()


@pytest.fixture(scope='function')
@pytest.mark.asyncio
async def entity_stan(app, event_loop, client_id):
    """Create a stan connection for each function.

    Uses environment variables for the cluster name.
    """
    nc = Nats()
    sc = Stan()

    await nc.connect(io_loop=event_loop)

    cluster_name = os.getenv('NATS_CLUSTER_ID')

    if not cluster_name:
        raise ValueError('Missing env variable: NATS_CLUSTER_ID')

    await sc.connect(cluster_name, client_id, nats=nc)

    yield sc

    await sc.close()
    await nc.close()


@pytest.fixture(scope='function')
def future(event_loop):
    """Return a future that is used for managing function tests."""
    _future = asyncio.Future(loop=event_loop)
    return _future


@pytest.fixture
def create_mock_coro(mocker, monkeypatch):
    """Return a mocked coroutine, and optionally patch-it in."""
    def _create_mock_patch_coro(to_patch=None):
        """Return a mocked coroutine, and optionally patch-it in."""
        mock = mocker.Mock()

        async def _coro(*args, **kwargs):
            return mock(*args, **kwargs)

        if to_patch:  # <-- may not need/want to patch anything
            monkeypatch.setattr(to_patch, _coro)
        return mock, _coro

    return _create_mock_patch_coro


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
