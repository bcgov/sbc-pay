"""Google Bucket Poller."""

import base64
import json

from flask import current_app
from google.cloud import storage

from services.sftp import SFTPService


class GoogleBucketTask:
    """Relies on pay-jobs creating files in the processing bucket, should move them into processed after sftp upload."""

    client: storage.Client = None
    bucket: storage.Bucket = None

    @classmethod
    def poll_google_bucket_for_ejv_files(cls):
        """Check google bucket for ejv files that PAY-JOBS has created."""
        cls.initialize_storage_client()
        files = cls._get_processing_files()
        cls._upload_to_sftp(files)
        for file in files:
            cls._move_to_processed_folder(file)

    @classmethod
    def initialize_storage_client(cls):
        """Initialize google storage client / bucket for use."""
        ftp_poller_bucket_name = current_app.config.get("FTP_POLLER_BUCKET_NAME")
        json_text = base64.b64decode(current_app.config.get("GOOGLE_STORAGE_SA")).decode("utf-8")
        auth_json = json.loads(json_text, strict=False)
        cls.client = storage.Client.from_service_account_info(auth_json)
        cls.bucket = cls.client.bucket(ftp_poller_bucket_name)

    @classmethod
    def _get_processing_files(cls):
        """List out all files, so they can be moved to processed."""
        blobs = cls.bucket.list_blobs(prefix="cgi_processing/")
        files = []
        for blob in blobs:
            files.append(cls.bucket.blob(blob))
        current_app.logger.info(f"List of processing files: {blobs}")
        return files

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
            for file in files:
                current_app.logger.info(f"Uploading file: {file.name}")
                ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
                sftp_client.put(file, ftp_dir + "/" + file.name)
