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

import pytest
from flask_migrate import Migrate, upgrade
from google.api_core.exceptions import NotFound
from google.cloud import pubsub
from pay_api import db as _db
from pay_api.services.gcp_queue import GcpQueue
from sqlalchemy import event, text
from sqlalchemy_utils import create_database, database_exists, drop_database

from pay_queue import create_app


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


@pytest.fixture(scope='session', autouse=True)
def db(app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a session-wide initialised database."""
    with app.app_context():
        if database_exists(_db.engine.url):
            drop_database(_db.engine.url)
        create_database(_db.engine.url)
        _db.session().execute(text('SET TIME ZONE "UTC";'))
        pay_api_dir = os.path.abspath('.').replace('pay-queue', 'pay-api')
        pay_api_dir = os.path.join(pay_api_dir, 'migrations')
        Migrate(app, _db, directory=pay_api_dir)
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


@pytest.fixture(scope='function', autouse=True)
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


@pytest.fixture(scope='session', autouse=True)
def auto(docker_services, app):
    """Spin up docker containers."""
    if app.config['USE_DOCKER_MOCK']:
        docker_services.start('minio')
        docker_services.start('proxy')
        docker_services.start('paybc')
        docker_services.start('pubsub-emulator')


@pytest.fixture()
def mock_publish(monkeypatch):
    """Mock check_auth."""
    monkeypatch.setattr('pay_api.services.gcp_queue_publisher.publish_to_queue', lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def mock_queue_auth(mocker):
    """Mock queue authorization."""
    mocker.patch('pay_queue.external.gcp_auth.verify_jwt', return_value='')


@pytest.fixture(scope='session', autouse=True)
def initialize_pubsub(app):
    """Initialize pubsub emulator and respective publisher and subscribers."""
    os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'
    project = app.config.get('TEST_GCP_PROJECT_NAME')
    topics = app.config.get('TEST_GCP_TOPICS')
    push_config = pubsub.types.PushConfig(push_endpoint=app.config.get('TEST_PUSH_ENDPOINT'))
    publisher = pubsub.PublisherClient()
    subscriber = pubsub.SubscriberClient()
    with publisher, subscriber:
        for topic in topics:
            topic_path = publisher.topic_path(project, topic)
            try:
                publisher.delete_topic(topic=topic_path)
            except NotFound:
                pass
            publisher.create_topic(name=topic_path)
            subscription_path = subscriber.subscription_path(project,  f'{topic}_subscription')
            try:
                subscriber.delete_subscription(subscription=subscription_path)
            except NotFound:
                pass
            subscriber.create_subscription(
                request={
                    'name': subscription_path,
                    'topic': topic_path,
                    'push_config': push_config,
                }
            )


@pytest.fixture(autouse=True)
def mock_pub_sub_call(mocker):
    """Mock pub sub call."""
    class PublisherMock:
        """Publisher Mock."""

        def __init__(self, *args, **kwargs):
            pass

        def publish(self, *args, **kwargs):
            """Publish mock."""
            raise CancelledError('This is a mock')

    mocker.patch('google.cloud.pubsub_v1.PublisherClient', PublisherMock)