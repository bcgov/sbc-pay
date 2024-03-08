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
import csv
import io
import json
import os
from typing import List

from flask import current_app
from minio import Minio

async def helper_add_event_to_queue(file_name: str, message_type: str):
    """Add eft event to the Queue."""
    payload = {
        'fileName': file_name,
        'location': current_app.config['MINIO_BUCKET_NAME']
    }
    # TODO, should be a POST to the queue.

def create_and_upload_settlement_file(file_name: str, rows: List[List]):
    """Create settlement file, upload to minio and send event."""
    headers = ['Record type', 'Source Transaction Type', 'Source Transaction Number',
               'Application Id', 'Application Date', 'Application amount', 'Customer Account',
               'Target transaction type',
               'Target transaction Number', 'Target Transaction Original amount',
               'Target Transaction Outstanding Amount',
               'Target transaction status', 'Reversal Reason code', 'Reversal reason description']
    with open(file_name, mode='w') as cas_file:
        cas_writer = csv.writer(cas_file, quoting=csv.QUOTE_ALL)
        cas_writer.writerow(headers)
        for row in rows:
            cas_writer.writerow(row)

    with open(file_name, 'rb') as f:
        upload_to_minio(f.read(), file_name)


def create_and_upload_eft_file(file_name: str, rows: List[List]):
    """Create eft file, upload to minio and send event."""
    with open(file_name, mode='w') as eft_file:
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



async def helper_add_event_to_queue(old_identifier: str = 'T1234567890',
                                    new_identifier: str = 'BC1234567890'):
    """Add event to the Queue."""
    message_type = MessageType.INCORPORATION.value
    payload = {
        'filing': {
            'header': {'filingId': '12345678'},
            'business': {'identifier': 'BC1234567'}
        },
        'identifier': new_identifier,
        'tempidentifier': old_identifier,
    }

    # TODO http post to application
