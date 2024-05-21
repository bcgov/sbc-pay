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
"""Common setup and fixtures for the pytest suite used by this service."""
import os
from contextlib import contextmanager

import pytest
from flask_migrate import Migrate, upgrade
from pay_api import db as _db
from pay_api.services.gcp_queue import GcpQueue
from sqlalchemy import event, text
from sqlalchemy.schema import DropConstraint, MetaData

from pay_queue import create_app


@contextmanager
def not_raises(exception):
    """Corallary to the pytest raises builtin.

    Assures that an exception is NOT thrown.
    """
    try:
        yield
    except exception: # NOQA
        raise pytest.fail(f'DID RAISE {exception}')


@pytest.fixture(scope='session', autouse=True)
def app():
    """Return a session-wide application configured in TEST mode."""
    _app = create_app('testing')
    return _app


@pytest.fixture(scope='function', autouse=True)
def gcp_queue(app, mocker):
    """Mock GcpQueue to avoid initializing the external connections."""
    mocker.patch.object(GcpQueue, 'init_app')
    return GcpQueue(app)


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

        # even though this isn't referenced directly, it sets up the internal configs that upgrade
        import sys
        migrations_path = [folder for folder in sys.path if 'pay-api/pay-api' in folder]
        if len(migrations_path) > 0:
            migrations_path = migrations_path[0].replace('/pay-api/src', '/pay-api/migrations')
        # Fix for windows.
        else:
            migrations_path = os.path.abspath('../../pay-api/migrations')

        Migrate(app, _db, directory=migrations_path)
        upgrade()

        return _db


@pytest.fixture
def config(app):
    """Return the application config."""
    return app.config


@pytest.fixture(scope='session')
def client(app):  # pylint: disable=redefined-outer-name
    """Return a session-wide Flask test client."""
    return app.test_client()


@pytest.fixture(scope='session')
def client_ctx(app):  # pylint: disable=redefined-outer-name
    """Return session-wide Flask test client."""
    with app.test_client() as _client:
        yield _client


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


@pytest.fixture(scope='session', autouse=True)
def auto(docker_services, app):
    """Spin up docker containers."""
    if app.config['USE_DOCKER_MOCK']:
        docker_services.start('minio')
        docker_services.start('proxy')
        docker_services.start('paybc')


@pytest.fixture(autouse=True)
def mock_queue_auth(mocker):
    """Mock queue authorization."""
    mocker.patch('pay_queue.external.gcp_auth.verify_jwt', return_value='')


@pytest.fixture(autouse=True)
def mock_publish(monkeypatch):
    """Mock check_auth."""
    monkeypatch.setattr('pay_api.services.gcp_queue_publisher.publish_to_queue', lambda *args, **kwargs: None)


# @pytest.fixture(scope='session', autouse=True)
# def initialize_pubsub(app):
#     """Initialize pubsub emulator and respective publisher and subscribers."""
#     os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'
#     project = app.config.get('TEST_GCP_PROJECT_NAME')
#     topics = app.config.get('TEST_GCP_TOPICS')
#     push_config = pubsub.types.PushConfig(push_endpoint=app.config.get('TEST_PUSH_ENDPOINT'))
#     publisher = pubsub.PublisherClient()
#     subscriber = pubsub.SubscriberClient()
#     with publisher, subscriber:
#         for topic in topics:
#             topic_path = publisher.topic_path(project, topic)
#             try:
#                 publisher.delete_topic(topic=topic_path)
#             except NotFound:
#                 pass
#             publisher.create_topic(name=topic_path)
#             subscription_path = subscriber.subscription_path(project,  f'{topic}_subscription')
#             try:
#                 subscriber.delete_subscription(subscription=subscription_path)
#             except NotFound:
#                 pass
#             subscriber.create_subscription(
#                 request={
#                     'name': subscription_path,
#                     'topic': topic_path,
#                     'push_config': push_config,
#                 }
#             )
