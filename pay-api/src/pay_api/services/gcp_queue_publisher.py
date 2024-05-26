"""This module provides Queue type services."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import uuid

from flask import current_app
from simple_cloudevent import SimpleCloudEvent

from pay_api.services.gcp_queue import GcpQueue, queue


@dataclass
class QueueMessage:
    """Queue message data class."""

    source: str
    message_type: str
    payload: dict
    topic: str
    ordering_key: Optional[str] = None


def publish_to_queue(queue_message: QueueMessage):
    """Publish to GCP PubSub Queue using queue."""
    if queue_message.topic is None:
        current_app.logger.info('Skipping queue message topic not set.')
        return

    # Create a SimpleCloudEvent from the QueueMessage
    cloud_event = SimpleCloudEvent(
        id=str(uuid.uuid4()),
        source=f'sbc-pay-{queue_message.source}',
        # Intentionally blank, this field has been moved to topic.
        subject=None,
        time=datetime.now(tz=timezone.utc).isoformat(),
        type=queue_message.message_type,
        data=queue_message.payload
    )

    kwargs = {}
    if queue_message.ordering_key:
        kwargs.update({'ordering_key': queue_message.ordering_key})
    queue.publish(queue_message.topic, GcpQueue.to_queue_message(cloud_event), **kwargs)
