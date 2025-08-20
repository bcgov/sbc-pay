"""Google Bucket Poller."""

import os
import traceback

from flask import current_app
from pay_api.services.google_bucket_service import GoogleBucketService

from services.sftp import SFTPService


class GoogleBucketPollerTask:
    """Relies on pay-jobs creating files in the processing bucket, should move them into processed after sftp upload."""

    @staticmethod
    def poll_google_bucket_for_ejv_files():
        """Check google bucket for ejv files that PAY-JOBS has created."""
        try:
            current_app.logger.info("Polling Google bucket for EJV files.")
            google_storage_client = GoogleBucketService.get_client()
            bucket = GoogleBucketService.get_bucket(google_storage_client, current_app.config.get("GOOGLE_BUCKET_NAME"))
            file_paths = GoogleBucketService.get_files_from_bucket_folder(
                bucket, current_app.config.get("GOOGLE_BUCKET_FOLDER_CGI_PROCESSING")
            )
            GoogleBucketPollerTask._upload_to_sftp(file_paths)
            GoogleBucketPollerTask._move_to_processed_folder(bucket, file_paths)
        except Exception as e:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(f"{{error: {str(e)}, stack_trace: {traceback.format_exc()}}}")

    @staticmethod
    def _move_to_processed_folder(bucket, file_paths):
        """Move files from processing to processed folder."""
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            GoogleBucketService.move_file_in_bucket(
                bucket,
                current_app.config.get("GOOGLE_BUCKET_FOLDER_CGI_PROCESSING"),
                current_app.config.get("GOOGLE_BUCKET_FOLDER_CGI_PROCESSED"),
                file_name,
            )

    @staticmethod
    def _upload_to_sftp(file_paths):
        """Handle SFTP upload for these files."""
        if not file_paths:
            return
        current_app.logger.info("Uploading files via SFTP to CAS.")
        with SFTPService.get_connection("CGI") as sftp_client:
            for file_path in file_paths:
                current_app.logger.info(f"Uploading file: {file_path}")
                ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
                target_file = os.path.basename(file_path)
                sftp_client.chdir(ftp_dir)
                sftp_client.put(file_path, target_file)
                current_app.logger.info(f"Uploaded file from: {file_path} to {ftp_dir}/{target_file}")
                os.remove(file_path)
        current_app.logger.info("Uploading files via SFTP done.")
