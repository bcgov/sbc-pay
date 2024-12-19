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
"""Utility functions for sFTP."""
import base64
import json

from flask import current_app
from google.cloud import storage


def upload_to_bucket(local_file_path: str, trg_file_path: str):
    """Upload files to ftp-poller bucket for processing."""
    ftp_poller_bucket_name = current_app.config.get("FTP_POLLER_BUCKET_NAME")
    json_text = base64.b64decode(current_app.config.get("GOOGLE_STORAGE_SA")).decode("utf-8")
    auth_json = json.loads(json_text, strict=False)
    client = storage.Client.from_service_account_info(auth_json)
    current_app.logger.info("Connecting to bucket %s", ftp_poller_bucket_name)
    bucket = client.bucket(ftp_poller_bucket_name)
    current_app.logger.info("Uploading to processing folder.")

    def upload_blob_to_processing(file_path):
        blob = bucket.blob(f"processing/{file_path}")
        blob.upload_from_filename(file_path)
        current_app.logger.info("Upload of %s complete.", file_path)

    upload_blob_to_processing(local_file_path)
    upload_blob_to_processing(trg_file_path)
