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

from datetime import UTC, datetime
from unittest.mock import ANY, MagicMock, patch

import pytest
from dotenv import load_dotenv
from gcp_queue.gcp_queue import GcpQueue

from pay_api import create_app
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage, publish_to_queue
from pay_api.services.payment_transaction import PaymentTransaction
from pay_api.utils.dataclasses import PaymentToken
from pay_api.utils.enums import PaymentMethod, TransactionStatus


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
    payload = PaymentToken(55, TransactionStatus.COMPLETED.value, 55, "NRO").to_dict()
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


def test_payment_token_with_dates():
    """Test PaymentToken with payment_date and refund_date based on feature flag."""
    payment_date = datetime.now(tz=UTC)
    refund_date = datetime.now(tz=UTC)

    class MockInvoice:
        def __init__(self, payment_date, refund_date):
            self.id = 55
            self.filing_id = 55
            self.corp_type_code = "NRO"
            self.payment_date = payment_date
            self.refund_date = refund_date
            self.payment_method_code = PaymentMethod.DIRECT_PAY.value

    invoice = MockInvoice(payment_date, refund_date)

    with patch("pay_api.services.payment_transaction.flags.is_on", return_value=True):
        result_payload = PaymentTransaction.create_event_payload(invoice, TransactionStatus.COMPLETED.value)
        assert result_payload["id"] == 55
        assert result_payload["statusCode"] == TransactionStatus.COMPLETED.value
        assert result_payload["filingIdentifier"] == 55
        assert result_payload["corpTypeCode"] == "NRO"
        assert result_payload["productReleaseDate"] == payment_date.isoformat()
        assert result_payload["productReversalDate"] == refund_date.isoformat()

    with patch("pay_api.services.payment_transaction.flags.is_on", return_value=False):
        result_payload = PaymentTransaction.create_event_payload(invoice, TransactionStatus.COMPLETED.value)
        assert result_payload["id"] == 55
        assert result_payload["statusCode"] == TransactionStatus.COMPLETED.value
        assert result_payload["filingIdentifier"] == 55
        assert result_payload["corpTypeCode"] == "NRO"
        assert "productReleaseDate" not in result_payload
        assert "productReversalDate" not in result_payload

    invoice.payment_date = None
    invoice.refund_date = None
    with patch("pay_api.services.payment_transaction.flags.is_on", return_value=True):
        result_payload = PaymentTransaction.create_event_payload(invoice, TransactionStatus.COMPLETED.value)
        assert result_payload["id"] == 55
        assert result_payload["statusCode"] == TransactionStatus.COMPLETED.value
        assert result_payload["filingIdentifier"] == 55
        assert result_payload["corpTypeCode"] == "NRO"
        assert result_payload.get("productReleaseDate") is None
        assert result_payload.get("productReversalDate") is None
