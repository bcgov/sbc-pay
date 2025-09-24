# Copyright © 2025 Province of British Columbia
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

"""Test-Suite to ensure that the Google Bucket Service is working as expected."""

import base64
import json
import os
import tempfile
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

from pay_api.services.google_bucket_service import GoogleBucketService


def get_bucket(storage_client, bucket_name):
    """Get a Google Cloud Storage bucket."""
    bucket = storage_client.bucket(bucket_name)
    if bucket.exists():
        bucket.delete(force=True)
    bucket = GoogleBucketService.get_bucket(storage_client, bucket_name)
    return bucket


@pytest.fixture
def storage_client(app):
    """Create google storage client using emulator."""
    host_name = app.config.get("GCS_EMULATOR_HOST")
    client = storage.Client(
        project="test-project",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": host_name},
    )
    return client


@pytest.fixture
def temp_test_files() -> Iterator[list[str]]:
    """Create temporary test files."""
    files = []
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        for i in range(2):
            file_path = os.path.join(temp_dir, f"test_file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Test content for file {i}")
            files.append(file_path)
        yield files


def test_get_client(session, app) -> None:
    """Test getting storage client."""
    service_account_info = {}

    encoded_credentials = base64.b64encode(json.dumps(service_account_info).encode()).decode()
    app.config["GOOGLE_STORAGE_SA"] = encoded_credentials

    with patch("google.cloud.storage.Client.from_service_account_info") as mock_client_method:
        mock_client_instance = MagicMock()
        mock_client_method.return_value = mock_client_instance

        client = GoogleBucketService.get_client()

        mock_client_method.assert_called_once_with(service_account_info)
        assert client == mock_client_instance


def test_get_file_bytes_from_bucket_folder(session, storage_client, app) -> None:
    """Test getting file bytes from bucket folder."""
    bucket = get_bucket(storage_client, "test-bucket-get-files-bytes")
    folder_name = "test-folder"
    file_name = "abc.txt"
    test_content = b"Test content for download"

    GoogleBucketService.upload_file_bytes_to_bucket_folder(bucket, folder_name, file_name, test_content)

    downloaded_bytes = GoogleBucketService.get_file_bytes_from_bucket_folder(bucket, folder_name, file_name)

    assert downloaded_bytes == test_content

    # clean up
    bucket.delete(force=True)


def test_upload_to_bucket_folder(session, storage_client, temp_test_files: list[str], app: Flask) -> None:
    """Testing upload_to_bucket_folder."""
    bucket = get_bucket(storage_client, "test-bucket-upload-files")
    folder_name = "test-folder"

    for file_path in temp_test_files:
        GoogleBucketService.upload_to_bucket_folder(bucket, folder_name, file_path)

    for file_path in temp_test_files:
        blob_name = f"{folder_name}/{os.path.basename(file_path)}"
        blob = bucket.blob(blob_name)
        assert blob.exists()

        downloaded_content = blob.download_as_text()
        with open(file_path) as f:
            original_content = f.read()
        assert downloaded_content == original_content
        blob.delete()

    bucket.delete(force=True)


def test_upload_file_bytes_to_bucket_folder(session, storage_client, app: Flask) -> None:
    """Test uploading file bytes to bucket folder."""
    bucket = get_bucket(storage_client, "test-bucket-upload-file-bytes")
    folder_name = "test-folder"
    file_name = "abc.txt"
    test_content = b"Test content for download"

    GoogleBucketService.upload_file_bytes_to_bucket_folder(bucket, folder_name, file_name, test_content)

    blob = bucket.blob(f"{folder_name}/{file_name}")
    assert blob.exists()

    # clean up
    bucket.delete(force=True)


def test_get_files_from_bucket_folder(session, storage_client, app: Flask) -> None:
    """Test getting files from bucket folder."""
    bucket = get_bucket(storage_client, "test-bucket-get-files")
    folder_name = "test-folder"

    test_files = {
        "file1.txt": b"Content of file 1",
        "file2.txt": b"Content of file 2",
        "subfolder/file3.txt": b"Content of file 3",
    }

    for file_name, content in test_files.items():
        GoogleBucketService.upload_file_bytes_to_bucket_folder(bucket, folder_name, file_name, content)

    # this should be ignored as it's a different folder
    folder_name_2 = "another-folder-2"
    folder_name_2_file_name = "abc.txt"
    GoogleBucketService.upload_file_bytes_to_bucket_folder(
        bucket, folder_name_2, folder_name_2_file_name, b"Content of abc.txt"
    )

    downloaded_files = GoogleBucketService.get_files_from_bucket_folder(bucket, folder_name)

    assert len(downloaded_files) == 3

    for file_path in downloaded_files:
        file_name = os.path.basename(file_path)
        assert file_name in test_files or any(k.endswith(file_name) for k in test_files)

    # clean up
    bucket.delete(force=True)


def test_move_file_in_bucket(session, storage_client, app: Flask) -> None:
    """Test moving a file in bucket."""
    bucket = get_bucket(storage_client, "test-bucket-move-file")
    source_folder = "source-folder"
    destination_folder = "destination-folder"
    file_name = "abc.txt"
    file_content = b"Content to be moved"

    GoogleBucketService.upload_file_bytes_to_bucket_folder(bucket, source_folder, file_name, file_content)

    source_blob = bucket.blob(f"{source_folder}/{file_name}")
    assert source_blob.exists()

    GoogleBucketService.move_file_in_bucket(bucket, source_folder, destination_folder, file_name)
    assert not source_blob.exists()
    destination_blob = bucket.blob(f"{destination_folder}/{file_name}")
    assert destination_blob.exists()

    # clean up
    bucket.delete(force=True)
