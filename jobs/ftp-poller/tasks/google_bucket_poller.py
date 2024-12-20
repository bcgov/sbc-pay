"""Google Bucket Poller."""

import base64
import json
import os
import tempfile

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
        cls.initialize_storage_client()
        files = cls._get_processing_files()
        cls._upload_to_sftp(files)
        cls._move_to_processed_folder(files)

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
        """Download all files, so they can be SFTP'd and moved to processed."""
        files = []
        for blob in cls.bucket.list_blobs(prefix="cgi_processing/"):
            # Skip if folder.
            if blob.name.endswith('/'):
                continue
            target_path = f"{tempfile.gettempdir()}/{blob.name.split('/')[-1]}"
            current_app.logger.info(f"Downloading {blob.name} to {target_path}")
            blob.download_to_filename(target_path)
            files.append(target_path)
        current_app.logger.info(f"List of processing files: {files}")
        return files

    @classmethod
    def _move_to_processed_folder(cls, files):
        """Move files from processing to processed folder."""
        for file in files:
            file = os.path.basename(file)
            current_app.logger.info(f"Moving {file} from processing to processed folder.")
            source_blob = cls.bucket.blob(f"cgi_processing/{file}")
            destination = f"cgi_processed/{file}"
            cls.bucket.copy_blob(source_blob, cls.bucket, destination)
            source_blob.delete()
            current_app.logger.info(f"File moved to cgi_processed/{file}")

    @classmethod
    def _upload_to_sftp(cls, files):
        """Handle SFTP upload for these files."""
        current_app.logger.info("Uploading via SFTP to CAS.")
        with SFTPService.get_connection("CGI") as sftp_client:
            for file in files:
                current_app.logger.info(f"Uploading file: {file.name}")
                ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
                sftp_client.put(file, ftp_dir + "/" + file.name)
                current_app.logger.info(f"Uploaded file: {file.name}")
