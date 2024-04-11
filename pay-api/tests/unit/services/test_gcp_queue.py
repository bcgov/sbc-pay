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
from unittest.mock import MagicMock, patch

from flask import current_app
import pytest
from pay_api.services.gcp_queue.gcp_queue_message import QueueMessage, publish_to_queue

# Sample data for testing
SAMPLE_QUEUE_MESSAGE = QueueMessage(
    source='test-source',
    message_type='test-message-type',
    payload={'key': 'value'},
    topic='projects/project-id/topics/topic'
)


@pytest.fixture
def mock_publisher_client():
    """Mock Publisher."""
    with patch('google.cloud.pubsub_v1.PublisherClient') as mock:
        yield mock


@pytest.fixture
def mock_credentials():
    """Mock Credentials."""
    with patch('google.auth.jwt.Credentials') as mock:
        mock.from_service_account_info.return_value = MagicMock()
        yield mock


def test_publish_to_queue_success(mock_publisher_client, mock_credentials):
    """Test that publish_to_queue successfully publishes a message to the queue."""
    # Mock the publish method to return a future object with a result method
    future_mock = MagicMock()
    future_mock.result.return_value = 'message_id'
    mock_publisher_client.return_value.publish.return_value = future_mock

    # Call the function under test
    publish_to_queue(SAMPLE_QUEUE_MESSAGE, current_app)

    mock_publisher_client.return_value.publish.assert_called_once()


def test_publish_to_queue_no_topic(mock_publisher_client, mock_credentials):
    """Test that publish_to_queue does not attempt to publish if no topic is set."""
    message_without_topic = QueueMessage(
        source='test-source',
        message_type='test-message-type',
        payload={'key': 'value'},
        topic=None  # No topic provided
    )

    publish_to_queue(message_without_topic, current_app)

    mock_publisher_client.return_value.publish.assert_not_called()
