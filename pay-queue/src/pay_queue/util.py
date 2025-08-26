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
"""Google bucket util functions."""

from flask import current_app
from pay_api.services.google_bucket_service import GoogleBucketService


def get_google_bucket():
    """Get a Google Cloud Storage bucket."""
    google_storage_client = GoogleBucketService.get_client()
    bucket_name = current_app.config.get("GOOGLE_BUCKET_NAME")
    bucket = GoogleBucketService.get_bucket(google_storage_client, bucket_name)
    return bucket


def get_object_from_bucket_folder(bucket_folder_name, file_name) -> bytes:
    """Get object from Google bucket folder."""
    bucket = get_google_bucket()
    return GoogleBucketService.get_file_bytes_from_bucket_folder(bucket, bucket_folder_name, file_name)
