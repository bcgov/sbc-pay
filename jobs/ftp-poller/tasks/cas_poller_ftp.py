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
"""Service to manage PAYBC services."""
import traceback
from typing import List

from flask import current_app
from paramiko.sftp_attr import SFTPAttributes

from services.sftp import SFTPService
from utils.utils import publish_to_queue, upload_to_minio


class CASPollerFtpTask:  # pylint:disable=too-few-public-methods
    """Task to Poll FTP."""

    @classmethod
    def poll_ftp(cls):
        """Poll SFTP.

        Steps:
        1. List Files.
        2. If file exists ,
                copy to minio
                archive to back up folder
                send jms message
        """
        payment_file_list: List[str] = []
        with SFTPService.get_connection() as sftp_client:
            try:
                ftp_dir: str = current_app.config.get("CAS_SFTP_DIRECTORY")
                file_list: List[SFTPAttributes] = sftp_client.listdir_attr(ftp_dir)
                current_app.logger.info(f"Found {len(file_list)} to be copied.")
                for file in file_list:
                    file_name = file.filename
                    file_full_name = ftp_dir + "/" + file_name
                    current_app.logger.info(f"Processing file  {file_full_name} started-----.")
                    if CASPollerFtpTask._is_valid_payment_file(sftp_client, file_full_name):
                        upload_to_minio(file, file_full_name, sftp_client, current_app.config["MINIO_BUCKET_NAME"])
                        payment_file_list.append(file_name)

                if len(payment_file_list) > 0:
                    CASPollerFtpTask._post_process(sftp_client, payment_file_list)

            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(f"{{error: {str(e)}, stack_trace: {traceback.format_exc()}}}")
        return payment_file_list

    @classmethod
    def _post_process(cls, sftp_client, payment_file_list: List[str]):
        """
        Post processing of the file.

        1.Move the file to backup folder
        2.Send a message to queue
        """
        cls._move_file_to_backup(sftp_client, payment_file_list)
        publish_to_queue(payment_file_list)

    @classmethod
    def _move_file_to_backup(cls, sftp_client, payment_file_list):
        ftp_backup_dir: str = current_app.config.get("CAS_SFTP_BACKUP_DIRECTORY")
        ftp_dir: str = current_app.config.get("CAS_SFTP_DIRECTORY")
        for file_name in payment_file_list:
            sftp_client.rename(ftp_dir + "/" + file_name, ftp_backup_dir + "/" + file_name)

    @classmethod
    def _is_valid_payment_file(cls, sftp_client, file_name):
        return sftp_client.isfile(file_name)
