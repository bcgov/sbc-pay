"""Google Bucket Poller"""

import base64
import json

from flask import current_app
from google.cloud import storage


class GoogleBucketTask:
    """Relies on pay-jobs creating files in the processing bucket, should move them into processed after sftp upload."""

    client: storage.Client = None
    bucket: storage.Client.bucket = None

    @classmethod
    def poll_google_bucket_for_ejv_files(cls):
        """Check google bucket for ejv files that PAY-JOBS has created."""
        cls.initialize_storage_client()
        files = cls._get_processing_files()
        for file in files:
            cls._move_to_processed_folder(file)
        cls._upload_to_sftp(files)

    @classmethod
    def initialize_storage_client(cls):
        """Setup google storage client for use."""
        ftp_poller_bucket_name = current_app.config.get("FTP_POLLER_BUCKET_NAME")
        json_text = base64.b64decode(current_app.config.get("GOOGLE_STORAGE_SA")).decode("utf-8")
        auth_json = json.loads(json_text, strict=False)
        cls.client = storage.Client.from_service_account_info(auth_json)
        cls.bucket = cls.client.bucket(ftp_poller_bucket_name)

    @classmethod
    def _get_processing_files(cls):
        """List out all files, so they can be moved to processed."""
        blobs = cls.bucket.list_blobs(prefix="cgi_processing/")
        current_app.logger.info(f"List of processing files: {blobs}")
        return blobs

    @classmethod
    def _move_to_processed_folder(cls, name):
        """Move files from processing to processed folder."""
        current_app.logger.info("Moving from processing to processed folder.")
        source_blob = cls.bucket.blob(f"cgi_processing/{name}")
        cls.bucket.copy_blob(source_blob, cls.bucket, f"cgi_processed/{name}")
        source_blob.delete()
        print(f"File moved to cgi_processed/{name}")

    @classmethod
    def _upload_to_sftp(cls, files):
        """Handle SFTP upload for these files."""
        current_app.logger.info("Uploading via SFTP to CAS.")
        with SFTPService.get_connection("CGI") as sftp_client:
            ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
            
