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

import time

import pytest
from invoke_jobs import create_app


@pytest.fixture(scope='session')
def app():
    """Return a session-wide application configured in TEST mode."""
    return create_app('testing')


@pytest.fixture(scope='function', autouse=True)
def session(app):  # pylint: disable=redefined-outer-name, invalid-name
    """Return a function-scoped session."""
    with app.app_context():
        yield app


@pytest.fixture(scope='session', autouse=True)
def auto(docker_services, app):  # pylint: disable=redefined-outer-name
    """Spin up docker instances."""
    if app.config['USE_DOCKER_MOCK']:
        docker_services.start('proxy')
        docker_services.start('sftp')
        time.sleep(2)


@pytest.fixture(scope='session')
def docker_compose_files(pytestconfig):
    """Get the docker-compose.yml absolute path."""
    import os  # pylint: disable=import-outside-toplevel
    return [
        os.path.join(str(pytestconfig.rootdir), 'tests/docker', 'docker-compose.yml')
    ]
