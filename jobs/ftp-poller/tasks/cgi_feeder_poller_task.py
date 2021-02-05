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

from services.sftp import SFTPService
from utils.utils import publish_to_queue, upload_to_minio


class CGIFeederPollerTask:  # pylint:disable=too-few-public-methods
    """Task to Poll FTP."""

    @classmethod
    def poll_ftp(cls):
        """Poll SFTP.

        Steps:
        1. List Files.
        2. If TRG , find its assoicated data file and do the operations.
        """
        payment_file_list: List[str] = []
        with SFTPService.get_connection() as sftp_client:
            try:
                ftp_dir: str = current_app.config.get('EJV_SFTP_DIRECTORY')
                file_list: List[SFTPAttributes] = sftp_client.listdir_attr(ftp_dir)
                current_app.logger.info(f'Found {len(file_list)} to be processed.')
                for file in file_list:
                    # process only trigger files.other files are derived from trigger files
                    if not cls._is_a_valid_trigger_file(file.filename):
                        continue
                    trg_file_name = file.filename
                    data_file_name = cls._get_data_file_name_from_trigger_file(trg_file_name)
                    data_file_full_name = ftp_dir + '/' + data_file_name
                    file_exists = sftp_client.exists(data_file_full_name) and sftp_client.isfile(
                        data_file_full_name)
                    if file_exists:
                        # ACK file Trigger events and move the files
                        if cls._is_ack_file(data_file_name):
                            # ACK files dont need to be copied to mino.
                            # publish to queue and add to back up list
                            publish_to_queue([data_file_name])
                            cls._move_file_to_backup(sftp_client, [trg_file_name, data_file_name])
                        if cls._is_feedback_file(data_file_name):
                            # feedback files ;copy to minio .publish to queu.back up list
                            data_file_attributes = sftp_client.stat(data_file_full_name)
                            upload_to_minio(data_file_attributes, data_file_full_name, sftp_client)
                            publish_to_queue([data_file_name])
                            cls._move_file_to_backup(sftp_client, [trg_file_name, data_file_name])
                    else:
                        current_app.logger.warning(
                            f'No data file as {data_file_full_name} exists for the trigger file {trg_file_name}.')


            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(e)
        return payment_file_list

    @classmethod
    def _move_file_to_backup(cls, sftp_client, backup_file_list):
        ftp_backup_dir: str = current_app.config.get('CAS_SFTP_BACKUP_DIRECTORY')
        ftp_dir: str = current_app.config.get('CAS_SFTP_DIRECTORY')
        for file_name in backup_file_list:
            sftp_client.rename(ftp_dir + '/' + file_name, ftp_backup_dir + '/' + file_name)

    @classmethod
    def _is_valid_payment_file(cls, sftp_client, file_name):
        return sftp_client.isfile(file_name)

    @classmethod
    def _is_a_valid_trigger_file(cls, file_name: str):
        return file_name.endswith('.TRG')

    @classmethod
    def _is_ack_file(cls, file_name: str):
        return file_name.startswith('ACK')

    @classmethod
    def _is_feedback_file(cls, file_name: str):
        return file_name.startswith('FEEDBACK')

    @classmethod
    def _get_data_file_name_from_trigger_file(cls, file_name: str) -> str:
        return file_name.replace('.TRG', '')
