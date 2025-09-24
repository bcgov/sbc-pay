# Copyright © 2025 Province of British Columbia
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
"""Service to manage Google Bucket."""

import base64
import json
import os
import tempfile

from attrs import define
from flask import current_app
from google.cloud import storage


@define
class GoogleBucketService:
    """Google Bucket Service wrapper."""

    @staticmethod
    def get_client() -> storage.Client:
        """Get a Google cloud storage client."""
        current_app.logger.info("Initializing Google Storage client.")
        json_text = base64.b64decode(current_app.config.get("GOOGLE_STORAGE_SA")).decode("utf-8")
        auth_json = json.loads(json_text, strict=False)
        client = storage.Client.from_service_account_info(auth_json)
        return client

    @staticmethod
    def get_bucket(client: storage.Client, bucket_name: str) -> storage.Bucket:
        """Get a Google bucket."""
        current_app.logger.info(f"Connecting to bucket {bucket_name}")
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            bucket.create()
        return bucket

    @staticmethod
    def get_files_from_bucket_folder(bucket: storage.Bucket, folder_name: str) -> list[str]:
        """Get a list of files in a Google bucket folder."""
        current_app.logger.info(f"Getting files from bucket folder {folder_name}.")
        blobs = bucket.list_blobs(prefix=f"{folder_name}/")
        file_paths = []
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            target_path = f"{tempfile.gettempdir()}/{blob.name.split('/')[-1]}"
            current_app.logger.info(f"Downloading {blob.name} to {target_path}")
            blob.download_to_filename(target_path)
            file_paths.append(target_path)
        return file_paths

    @staticmethod
    def get_file_bytes_from_bucket_folder(bucket, folder_name, file_name: str):
        """Get file bytes from Google bucket."""
        blob_name = f"{folder_name}/{file_name}"
        blob = bucket.blob(blob_name)
        file_bytes = blob.download_as_bytes()
        return file_bytes

    @staticmethod
    def upload_to_bucket_folder(bucket: storage.Bucket, folder_name: str, file_path: str):
        """Upload file to Google bucket."""
        current_app.logger.info(f"Uploading {file_path} to bucket {bucket.name}/{folder_name}/")
        current_app.logger.info("Uploading to processing folder.")

        blob = bucket.blob(f"{folder_name}/{os.path.basename(file_path)}")
        blob.upload_from_filename(file_path)
        current_app.logger.info(f"Upload of {file_path} to bucket {bucket.name}/{folder_name}/ completed")

    @staticmethod
    def upload_file_bytes_to_bucket_folder(bucket: storage.Bucket, folder_name: str, file_name: str, file_bytes: bytes):
        """Upload file bytes to Google bucket."""
        current_app.logger.info(f"Uploading {file_name} content to bucket {bucket.name}/{folder_name}/")

        blob = bucket.blob(f"{folder_name}/{file_name}")
        data = bytes(file_bytes)
        blob.upload_from_string(data, content_type="application/octet-stream")
        current_app.logger.info(f"Upload of {file_name} content to bucket {bucket.name}/{folder_name}/ completed.")

    @staticmethod
    def move_file_in_bucket(
        bucket: storage.Bucket, source_folder_name: str, destination_folder_name: str, file_name: str
    ):
        """Move a file from one folder to another in Google bucket."""
        current_app.logger.info(
            f"Moving {source_folder_name}/{file_name} to {destination_folder_name}/{file_name} in bucket {bucket.name}"
        )

        source_blob = bucket.blob(f"{source_folder_name}/{file_name}")
        destination_path = f"{destination_folder_name}/{file_name}"
        bucket.copy_blob(source_blob, bucket, destination_path)
        source_blob.delete()
        current_app.logger.info(
            f"Move of {source_folder_name}/{file_name} to {destination_folder_name}/{file_name} "
            f"in bucket {bucket.name} completed."
        )
