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

"""Tests to assure the GCP service layer.

Test-Suite to ensure that the GCP Queue Service layer is working as expected.
"""

from dataclasses import asdict
from unittest.mock import ANY, MagicMock, patch

import humps
import pytest
from dotenv import load_dotenv
from gcp_queue.gcp_queue import GcpQueue

from pay_api import create_app
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage, publish_to_queue
from pay_api.services.payment_transaction import PaymentToken
from pay_api.utils.enums import TransactionStatus


@pytest.fixture()
def mock_publisher_client():
    """Mock the PublisherClient used in GcpQueue."""
    with patch("google.cloud.pubsub_v1.PublisherClient") as publisher:
        yield publisher.return_value


@pytest.fixture()
def mock_credentials():
    """Mock Credentials."""
    with patch("google.auth.jwt.Credentials") as mock:
        mock.from_service_account_info.return_value = MagicMock()
        yield mock


def test_publish_to_queue_success(app, mock_credentials, mock_publisher_client):
    """Test publishing to GCP PubSub Queue successfully."""
    with patch.object(GcpQueue, "publish") as mock_publisher:
        with app.app_context():
            queue_message = QueueMessage(
                source="test-source",
                message_type="test-message-type",
                payload={"key": "value"},
                topic="projects/project-id/topics/topic",
            )

            publish_to_queue(queue_message)
            mock_publisher.assert_called_once_with("projects/project-id/topics/topic", ANY)


def test_publish_to_queue_no_topic(app, mock_credentials, mock_publisher_client):
    """Test that publish_to_queue does not publish if no topic is set."""
    with patch.object(GcpQueue, "publish") as mock_publisher:
        with app.app_context():
            queue_message = QueueMessage(
                source="test-source",
                message_type="test-message-type",
                payload={"key": "value"},
                topic=None,
            )
            publish_to_queue(queue_message)
            mock_publisher.publish.assert_not_called()


@pytest.mark.skip(reason="ADHOC only test.")
def test_gcp_pubsub_connectivity(monkeypatch):
    """Test that a queue can publish to gcp pubsub."""
    # We don't want any of the monkeypatches by the fixtures.
    monkeypatch.undo()
    load_dotenv(".env")
    app_prod = create_app("production")
    payload = humps.camelize(asdict(PaymentToken(55, TransactionStatus.COMPLETED.value, 55, "NRO")))
    with app_prod.app_context():
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source="test",
                message_type="bc.registry.payment",
                payload=payload,
                topic=app_prod.config.get("NAMEX_PAY_TOPIC"),
            )
        )
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source="test",
                message_type="test",
                payload={"key": "value"},
                topic=app_prod.config.get("ACCOUNT_MAILER_TOPIC"),
            )
        )
