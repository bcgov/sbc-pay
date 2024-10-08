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
from typing import List

from flask import current_app
from paramiko.sftp_attr import SFTPAttributes
from sbc_common_components.utils.enums import QueueMessageTypes

from services.sftp import SFTPService
from utils import utils


class CGIFeederPollerTask:  # pylint:disable=too-few-public-methods
    """Task to Poll FTP."""

    @classmethod
    def poll_ftp(cls):
        """Poll SFTP.

        Steps:
        1. List Files.
        2. If TRG , find its associated data file and do the operations.
        """
        with SFTPService.get_connection("CGI") as sftp_client:
            try:
                ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
                file_list: List[SFTPAttributes] = sftp_client.listdir_attr(ftp_dir)

                current_app.logger.info(
                    f"Found {len(file_list)} to be processed.This includes all files in the folder."
                )
                for file in file_list:
                    file_name = file.filename
                    file_full_name = ftp_dir + "/" + file_name
                    if not sftp_client.isfile(file_full_name):  # skip directories
                        current_app.logger.info(f"Skipping directory {file_name}.")
                        continue
                    if cls._is_ack_file(file_name):
                        utils.publish_to_queue([file_name], QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)
                        cls._move_file_to_backup(sftp_client, [file_name])
                    elif cls._is_feedback_file(file_name):
                        bucket_name = current_app.config.get("MINIO_CGI_BUCKET_NAME")
                        utils.upload_to_minio(file, file_full_name, sftp_client, bucket_name)
                        utils.publish_to_queue(
                            [file_name], QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value, location=bucket_name
                        )
                        cls._move_file_to_backup(sftp_client, [file_name])
                    elif cls._is_a_trigger_file(file_name):
                        cls._remove_file(sftp_client, file_name)
                    else:
                        current_app.logger.warning(
                            f"Ignoring file found which is not trigger ACK or feedback {file_name}."
                        )

            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(e)

    @classmethod
    def _move_file_to_backup(cls, sftp_client, backup_file_list):
        ftp_backup_dir: str = current_app.config.get("CGI_SFTP_BACKUP_DIRECTORY")
        ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
        for file_name in backup_file_list:
            sftp_client.rename(ftp_dir + "/" + file_name, ftp_backup_dir + "/" + file_name)

    @classmethod
    def _remove_file(cls, sftp_client, file_name: str):
        ftp_dir: str = current_app.config.get("CGI_SFTP_DIRECTORY")
        current_app.logger.info(f"Removing file: {ftp_dir}/{file_name}")
        sftp_client.remove(ftp_dir + "/" + file_name)

    @classmethod
    def _is_a_trigger_file(cls, file_name: str):
        return file_name.endswith(current_app.config.get("CGI_TRIGGER_FILE_SUFFIX")) and not file_name.startswith(
            current_app.config.get("CGI_INBOX_FILE_PREFIX")
        )  # INBOX TRG is for them to listen

    @classmethod
    def _is_ack_file(cls, file_name: str):
        return file_name.startswith(current_app.config.get("CGI_ACK_FILE_PREFIX"))

    @classmethod
    def _is_feedback_file(cls, file_name: str):
        return file_name.startswith(current_app.config.get("CGI_FEEDBACK_FILE_PREFIX"))
