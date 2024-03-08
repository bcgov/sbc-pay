"""This module provides Queue type services."""
import base64
import dataclasses
import json
import uuid
from concurrent.futures import CancelledError
from concurrent.futures import TimeoutError  # pylint: disable=W0622
from datetime import datetime, timezone

from flask import current_app
from google.auth import jwt
from google.cloud import pubsub_v1
from simple_cloudevent import SimpleCloudEvent, to_queue_message


@dataclasses
class QueueMessage:
    """Queue message data class."""

    source: str
    subject: str
    message_type: str
    payload: dict
    topic: str


def publish_to_queue(queue_message: QueueMessage):
    """Publish to GCP PubSub Queue."""
    ce = SimpleCloudEvent(
        id=str(uuid.uuid4()),
        source=f'sbc-pay-{queue_message.source}',
        subject=queue_message.subject,
        time=datetime.now(tz=timezone.utc).isoformat(),
        type=queue_message.message_type,
        data=queue_message.payload
    )

    _send_to_queue(to_queue_message(ce), queue_message.topic)


def _send_to_queue(payload: bytes, topic_name: str):
    """Send payload to the queue."""
    if not ((gcp_auth_key := current_app.config.get('GCP_AUTH_KEY')) and
            (audience := current_app.config.get('AUDIENCE')) and
            topic_name and
            (publisher_audience := current_app.config.get('PUBLISHER_AUDIENCE'))):
        raise Exception('Missing setup arguments')  # pylint: disable=W0719

    try:
        service_account_info = json.loads(base64.b64decode(gcp_auth_key).decode('utf-8'))
        credentials = jwt.Credentials.from_service_account_info(
            service_account_info, audience=audience
        )
        credentials_pub = credentials.with_claims(audience=publisher_audience)
        publisher = pubsub_v1.PublisherClient(credentials=credentials_pub)
    except Exception as error:  # noqa: B902
        raise Exception('Unable to create a connection', error) from error  # pylint: disable=W0719

    try:
        future = publisher.publish(topic_name, payload)
        return future.result()
    except (CancelledError, TimeoutError) as error:
        raise Exception('Unable to post to queue', error) from error  # pylint: disable=W0719
