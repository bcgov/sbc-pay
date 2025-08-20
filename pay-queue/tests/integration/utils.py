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
"""Utilities used by the integration tests."""
import base64
import csv
import json
import uuid
from datetime import datetime, timezone
from socket import SO_REUSEADDR, SOL_SOCKET, socket
from time import sleep
from typing import List

from flask import current_app
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.services.google_bucket_service import GoogleBucketService
from pay_api.utils.enums import QueueSources
from sbc_common_components.utils.enums import QueueMessageTypes
from simple_cloudevent import SimpleCloudEvent, to_queue_message


def build_request_for_queue_push(message_type, payload):
    """Build request for queue message."""
    queue_message_bytes = to_queue_message(
        SimpleCloudEvent(
            id=str(uuid.uuid4()),
            source="pay-queue",
            subject=None,
            time=datetime.now(tz=timezone.utc).isoformat(),
            type=message_type,
            data=payload,
        )
    )

    return {
        "message": {"data": base64.b64encode(queue_message_bytes).decode("utf-8")},
        "subscription": "foobar",
    }


def post_to_queue(client, request_payload):
    """Post request to worker using an http request on our wrapped flask instance."""
    response = client.post(
        "/",
        data=json.dumps(request_payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200


def create_and_upload_settlement_file(file_name: str, rows: List[List]):
    """Create settlement file, upload to google bucket and send event."""
    headers = [
        "Record type",
        "Source Transaction Type",
        "Source Transaction Number",
        "Application Id",
        "Application Date",
        "Application amount",
        "Customer Account",
        "Target transaction type",
        "Target transaction Number",
        "Target Transaction Original amount",
        "Target Transaction Outstanding Amount",
        "Target transaction status",
        "Reversal Reason code",
        "Reversal reason description",
    ]
    with open(file_name, mode="w", encoding="utf-8") as cas_file:
        cas_writer = csv.writer(cas_file, quoting=csv.QUOTE_ALL)
        cas_writer.writerow(headers)
        for row in rows:
            cas_writer.writerow(row)

    with open(file_name, "rb") as f:
        upload_to_google_bucket(f.read(), file_name)


def create_and_upload_eft_file(file_name: str, rows: List[List]):
    """Create eft file, upload to google bucket and send event."""
    with open(file_name, mode="w", encoding="utf-8") as eft_file:
        for row in rows:
            print(row, file=eft_file)

    with open(file_name, "rb") as f:
        upload_to_google_bucket(f.read(), file_name)


def get_test_bucket(app):
    """Get a Google Cloud Storage bucket for testing with emulator."""
    host_name = app.config.get("GCS_EMULATOR_HOST")

    client = storage.Client(
        project="test-project",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": host_name},
    )

    bucket_name = app.config.get("GOOGLE_BUCKET_NAME")
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        bucket.create()
    return bucket


def upload_to_google_bucket(value_as_bytes, file_name: str):
    """Upload bytes to GCS bucket."""
    bucket = get_test_bucket(current_app)
    GoogleBucketService.upload_file_bytes_to_bucket_folder(bucket, "test-folder", file_name, value_as_bytes)


def forward_incoming_message_to_test_instance(session, app, client):
    """Forward incoming http message to test instance."""
    # Note this is a bit different than how the queue could behave, it could send multiples.
    # This just receives one HTTP request and forwards it to the test instance.
    # This is simpler than running another flask instance and tieing it to all the same as our unit tests.
    with socket() as server_socket:
        server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server_socket.settimeout(2)
        server_socket.bind(("0.0.0.0", current_app.config.get("TEST_PUSH_ENDPOINT_PORT")))
        server_socket.listen(10)
        tries = 100
        while tries > 0:
            client_socket, _ = server_socket.accept()
            if socket_data := client_socket.recv(4096):
                body = socket_data.decode("utf8").split("\r\n")[-1]
                payload = json.loads(body)
                post_to_queue(client, payload)
                client_socket.send("HTTP/1.1 200 OK\n\n".encode("utf8"))
                break
            sleep(0.01)
            tries -= 1
        assert tries > 0


def add_file_event_to_queue_and_process(client, file_name: str, message_type: str, use_pubsub_emulator=False):
    """Add event to the Queue."""
    queue_payload = {
        "fileName": file_name,
        "location": "test-folder",
    }
    if use_pubsub_emulator:
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.FTP_POLLER.value,
                message_type=message_type,
                payload=queue_payload,
                topic=f'projects/{current_app.config["TEST_GCP_PROJECT_NAME"]}/topics/ftp-poller-dev',
            )
        )
        forward_incoming_message_to_test_instance(client)
    else:
        payload = build_request_for_queue_push(message_type, queue_payload)
        post_to_queue(client, payload)


def helper_add_identifier_event_to_queue(
    client, old_identifier: str = "T1234567890", new_identifier: str = "BC1234567890"
):
    """Add event to the Queue."""
    message_type = QueueMessageTypes.INCORPORATION.value
    queue_payload = {
        "filing": {
            "header": {"filingId": "12345678"},
            "business": {"identifier": "BC1234567"},
        },
        "identifier": new_identifier,
        "tempidentifier": old_identifier,
    }
    request_payload = build_request_for_queue_push(message_type, queue_payload)
    post_to_queue(client, request_payload)
