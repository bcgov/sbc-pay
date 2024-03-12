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
"""Utilities used by the integration tests."""
import base64
import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import List

from flask import current_app
from minio import Minio
from pay_api.utils.enums import MessageType
from simple_cloudevent import SimpleCloudEvent, to_queue_message


def build_request_for_queue_message(message_type, payload):
    """Build request for queue message."""
    queue_message_bytes = to_queue_message(SimpleCloudEvent(
        id=str(uuid.uuid4()),
        source='pay-queue',
        subject=None,
        time=datetime.now(tz=timezone.utc).isoformat(),
        type=message_type,
        data=payload
    ))

    return {
        'message': {
            'data': base64.b64encode(queue_message_bytes).decode('utf-8')
        },
        'subscription': 'foobar'
    }


def post_to_queue(client, request_payload):
    """Post request to queue."""
    response = client.post('/', data=json.dumps(request_payload), headers={'Content-Type': 'application/json'})
    assert response.status_code == 200


def create_and_upload_settlement_file(file_name: str, rows: List[List]):
    """Create settlement file, upload to minio and send event."""
    headers = ['Record type', 'Source Transaction Type', 'Source Transaction Number',
               'Application Id', 'Application Date', 'Application amount', 'Customer Account',
               'Target transaction type',
               'Target transaction Number', 'Target Transaction Original amount',
               'Target Transaction Outstanding Amount',
               'Target transaction status', 'Reversal Reason code', 'Reversal reason description']
    with open(file_name, mode='w', encoding='utf-8') as cas_file:
        cas_writer = csv.writer(cas_file, quoting=csv.QUOTE_ALL)
        cas_writer.writerow(headers)
        for row in rows:
            cas_writer.writerow(row)

    with open(file_name, 'rb') as f:
        upload_to_minio(f.read(), file_name)


def create_and_upload_eft_file(file_name: str, rows: List[List]):
    """Create eft file, upload to minio and send event."""
    with open(file_name, mode='w', encoding='utf-8') as eft_file:
        for row in rows:
            print(row, file=eft_file)

    with open(file_name, 'rb') as f:
        upload_to_minio(f.read(), file_name)


def upload_to_minio(value_as_bytes, file_name: str):
    """Return a pre-signed URL for new doc upload."""
    minio_endpoint = current_app.config['MINIO_ENDPOINT']
    minio_key = current_app.config['MINIO_ACCESS_KEY']
    minio_secret = current_app.config['MINIO_ACCESS_SECRET']
    minio_client = Minio(minio_endpoint, access_key=minio_key, secret_key=minio_secret,
                         secure=current_app.config['MINIO_SECURE'])

    value_as_stream = io.BytesIO(value_as_bytes)
    minio_client.put_object(current_app.config['MINIO_BUCKET_NAME'], file_name, value_as_stream,
                            os.stat(file_name).st_size)


def helper_add_file_event_to_queue(client, file_name: str, message_type: str):
    """Add event to the Queue."""
    queue_payload = {
        'fileName': file_name,
        'location': current_app.config['MINIO_BUCKET_NAME']
    }
    request_payload = build_request_for_queue_message(message_type, queue_payload)
    post_to_queue(client, request_payload)


def helper_add_identifier_event_to_queue(client, old_identifier: str = 'T1234567890',
                                         new_identifier: str = 'BC1234567890'):
    """Add event to the Queue."""
    message_type = MessageType.INCORPORATION.value
    queue_payload = {
        'filing': {
            'header': {'filingId': '12345678'},
            'business': {'identifier': 'BC1234567'}
        },
        'identifier': new_identifier,
        'tempidentifier': old_identifier,
    }
    request_payload = build_request_for_queue_message(message_type, queue_payload)
    post_to_queue(client, request_payload)
