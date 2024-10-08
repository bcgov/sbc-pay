# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This module is a wrapper for Minio."""
import io

from flask import current_app
from minio import Minio
from urllib3 import HTTPResponse


def put_object(value_as_bytes, file_name: str, bucket_name, file_size: int = 0):
    """Return a pre-signed URL for new doc upload."""
    current_app.logger.debug(f"Creating pre-signed URL for {file_name}")
    minio_client: Minio = _get_client()
    value_as_stream = io.BytesIO(value_as_bytes)
    minio_client.put_object(bucket_name, file_name, value_as_stream, file_size)


def get_object(file_name: str) -> HTTPResponse:
    """Return a pre-signed URL for new doc upload."""
    current_app.logger.debug(f"Creating pre-signed URL for {file_name}")
    minio_client: Minio = _get_client()
    return minio_client.get_object(current_app.config["MINIO_BUCKET_NAME"], file_name)


def _get_client() -> Minio:
    """Return a minio client."""
    minio_endpoint = current_app.config["MINIO_ENDPOINT"]
    minio_key = current_app.config["MINIO_ACCESS_KEY"]
    minio_secret = current_app.config["MINIO_ACCESS_SECRET"]
    return Minio(
        minio_endpoint, access_key=minio_key, secret_key=minio_secret, secure=current_app.config["MINIO_SECURE"]
    )
