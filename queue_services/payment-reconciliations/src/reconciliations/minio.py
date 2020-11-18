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
"""Minio util functions."""

from flask import current_app
from minio import Minio
from urllib3 import HTTPResponse


def get_object(bucket_name: str, file_name: str) -> HTTPResponse:
    """Return a pre-signed URL for new doc upload."""
    current_app.logger.debug(f'Creating pre-signed URL for {file_name}')
    minio_endpoint = current_app.config['MINIO_ENDPOINT']
    minio_key = current_app.config['MINIO_ACCESS_KEY']
    minio_secret = current_app.config['MINIO_ACCESS_SECRET']

    minio_client: Minio = Minio(minio_endpoint, access_key=minio_key, secret_key=minio_secret,
                                secure=current_app.config['MINIO_SECURE'])

    return minio_client.get_object(bucket_name, file_name)
