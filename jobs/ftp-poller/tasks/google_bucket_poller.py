"""Google Bucket Poller."""

import base64
import json
import os
import tempfile
import traceback

from flask import current_app
from google.cloud import storage

from services.sftp import SFTPService


class GoogleBucketPollerTask:
    """Relies on pay-jobs creating files in the processing bucket, should move them into processed after sftp upload."""

    client: storage.Client = None
    bucket: storage.Bucket = None

    @classmethod
    def poll_google_bucket_for_ejv_files(cls):
        """Check google bucket for ejv files that PAY-JOBS has created."""
        try:
            cls.initialize_storage_client()
            file_paths = cls._get_processing_files()
            cls._upload_to_sftp(file_paths)
            cls._move_to_processed_folder(file_paths)
        except Exception as e:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(f"{{error: {str(e)}, stack_trace: {traceback.format_exc()}}}")

    @classmethod
    def initialize_storage_client(cls):
        """Initialize google storage client / bucket for use."""
        current_app.logger.info("Initializing Google Storage client.")
        ftp_poller_bucket_name = current_app.config.get("FTP_POLLER_BUCKET_NAME")
        json_text = base64.b64decode(current_app.config.get("GOOGLE_STORAGE_SA")).decode("utf-8")
        auth_json = json.loads(json_text, strict=False)
        cls.client = storage.Client.from_service_account_info(auth_json)
        cls.bucket = cls.client.bucket(ftp_poller_bucket_name)

    @classmethod
    def _get_processing_files(cls):
        """Download all files to temp folder, so they can be SFTP'd and moved to processed."""
        file_paths = []
        for blob in cls.bucket.list_blobs(prefix="cgi_processing/"):
            # Skip if folder.
            if blob.name.endswith("/"):
                continue
            target_path = f"{tempfile.gettempdir()}/{blob.name.split('/')[-1]}"
            current_app.logger.info(f"Downloading {blob.name} to {target_path}")
            blob.download_to_filename(target_path)
            file_paths.append(target_path)
        current_app.logger.info(f"List of processing files: {file_paths}")
        return file_paths

    @classmethod
    def _move_to_processed_folder(cls, file_paths):
        """Move files from processing to processed folder."""
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            current_app.logger.info(f"Moving {file_name} from processing to processed folder.")
            source_blob = cls.bucket.blob(f"cgi_processing/{file_name}")
            destination = f"cgi_processed/{file_name}"
            cls.bucket.copy_blob(source_blob, cls.bucket, destination)
            source_blob.delete()
            current_app.logger.info(f"File moved to cgi_processed/{file_name}")

    @classmethod
    def _upload_to_sftp(cls, file_paths):
        """Handle SFTP upload for these files."""
        if not file_paths:
            return
        current_app.logger.info("Uploading files via SFTP to CAS.")
        with SFTPService.get_connection("CGI") as sftp_client:
            for file_path in file_paths:
                current_app.logger.info(f"Uploading file: {file_path}")
                ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
                sftp_client.put(file_path, ftp_dir + "/" + file_path)
                current_app.logger.info(f"Uploaded file: {file_path}")
                os.remove(file_path)
        current_app.logger.info("Uploading files via SFTP done.")
