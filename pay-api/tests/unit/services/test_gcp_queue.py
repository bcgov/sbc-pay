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

"""Tests to assure the GCP service layer.

Test-Suite to ensure that the GCP Queue Service layer is working as expected.
"""
from unittest.mock import ANY, MagicMock, patch

import pytest
from flask import Flask

from pay_api.services.gcp_queue.gcp_queue import GcpQueue
from pay_api.services.gcp_queue_publisher import QueueMessage, publish_to_queue


@pytest.fixture(autouse=True)
def setup():
    """Initialize app with test env for testing."""
    global app
    app = Flask(__name__)
    app.env = 'testing'


@pytest.fixture(autouse=True)
def mock_publisher_client():
    """Mock the PublisherClient used in GcpQueue."""
    with patch('google.cloud.pubsub_v1.PublisherClient') as publisher:
        yield publisher.return_value


@pytest.fixture(autouse=True)
def mock_credentials():
    """Mock Credentials."""
    with patch('google.auth.jwt.Credentials') as mock:
        mock.from_service_account_info.return_value = MagicMock()
        yield mock


def test_publish_to_queue_success():
    """Test publishing to GCP PubSub Queue successfully."""
    with patch.object(GcpQueue, 'publish') as mock_publisher:
        with app.app_context():
            queue_message = QueueMessage(
                source='test-source',
                message_type='test-message-type',
                payload={'key': 'value'},
                topic='projects/project-id/topics/topic'
            )

            publish_to_queue(queue_message)
            mock_publisher.assert_called_once_with('projects/project-id/topics/topic', ANY)


def test_publish_to_queue_no_topic():
    """Test that publish_to_queue does not publish if no topic is set."""
    with patch.object(GcpQueue, 'publish') as mock_publisher:
        with patch.object(Flask, 'logger') as logger:
            with app.app_context():
                queue_message = QueueMessage(
                    source='test-source',
                    message_type='test-message-type',
                    payload={'key': 'value'},
                    topic=None
                )
                publish_to_queue(queue_message)
                mock_publisher.publish.assert_not_called()
                logger.info.assert_called_once_with('Skipping queue message topic not set.')
