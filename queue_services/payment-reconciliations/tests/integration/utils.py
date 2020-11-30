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

import stan
from flask import current_app
from minio import Minio


async def helper_add_event_to_queue(stan_client: stan.aio.client.Client,
                                    file_name: str):
    """Add event to the Queue."""
    payload = {
        'specversion': '1.x-wip',
        'type': 'bc.registry.payment.casSettlementUploaded',
        'source': 'https://api.business.bcregistry.gov.bc.ca/v1/accounts/1/',
        'id': 'C234-1234-1234',
        'time': '2020-08-28T17:37:34.651294+00:00',
        'datacontenttype': 'application/json',
        'data': {
            'fileName': file_name,
            'location': current_app.config['MINIO_BUCKET_NAME']
        }
    }

    await stan_client.publish(subject=current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                              payload=json.dumps(payload).encode('utf-8'))


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
