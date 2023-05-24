"""This module provides Queue type services."""
import base64
import json
import uuid
from concurrent.futures import CancelledError
from concurrent.futures import TimeoutError  # pylint: disable=W0622

from flask import current_app
from google.auth import jwt
from google.cloud import pubsub_v1
from simple_cloudevent import SimpleCloudEvent, to_queue_message

from .invoice import Invoice


def publish_to_queue(payload: dict, invoice: Invoice):
    """Publish a 'COMPLETED' invoice's info to the GCP PubSub Queue."""
    ce = SimpleCloudEvent()
    ce.id = payload.get('paymentToken', {}).get('id', str(uuid.uuid4()))
    ce.source = 'sbc-pay'
    ce.subject = invoice.business_identifier
    ce.time = invoice.payment_date
    ce.type = 'payment'
    ce.data = payload

    _send_to_queue(to_queue_message(ce))


def _send_to_queue(payload: bytes):
    """Send payload to the queue."""
    if not ((gcp_auth_key := current_app.config.get('GCP_AUTH_KEY')) and
            (audience := current_app.config.get('AUDIENCE')) and
            (topic_name := current_app.config.get('TOPIC_NAME')) and
            (publisher_audience := current_app.config.get('PUBLISHER_AUDIENCE'))):

        raise Exception('missing setup arguments')  # pylint: disable=W0719

    # get authenticated publisher
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
