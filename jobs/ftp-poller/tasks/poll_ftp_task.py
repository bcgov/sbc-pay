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
from datetime import datetime
from typing import List

from flask import current_app
from paramiko import SFTPFile
from paramiko.sftp_attr import SFTPAttributes
from pay_api.services.queue_publisher import publish_response

from utils.minio import MinioService
from utils.sftp import SFTPService


class PollFtpTask:  # pylint:disable=too-few-public-methods
    """Task to Poll FTP."""

    @classmethod
    def poll_ftp(cls):
        """Poll SFTP.

        Steps:
        1. List Files.
        2. If file
        """
        payment_file_list: List[str] = []
        try:

            ftp_dir: str = current_app.config.get('CAS_SFTP_DIRECTORY')
            sftp_client = SFTPService.get_connection()

            file_list: List[SFTPAttributes] = sftp_client.listdir_attr(ftp_dir)
            current_app.logger.info(f'Found {len(file_list)} to be copied.')
            for file in file_list:
                file_name = file.filename
                file_full_name = ftp_dir + '/' + file_name
                current_app.logger.info(f'Processing file  {file_full_name} started-----.')
                if PollFtpTask._is_valid_payment_file(file_full_name):
                    cls.upload_to_minio(file, file_full_name, sftp_client)
                    payment_file_list.append(file_name)

            if len(payment_file_list) > 0:
                PollFtpTask._post_process(payment_file_list)

        except Exception as e:  # pylint: disable=broad-except
            current_app.logger.error(e)
        finally:
            SFTPService.get_connection().close()
        return payment_file_list

    @classmethod
    def upload_to_minio(cls, file, file_full_name, sftp_client):
        f: SFTPFile
        with sftp_client.open(file_full_name) as f:
            f.prefetch()
            value_as_bytes = f.read()
            try:
                MinioService.put_object(value_as_bytes, file.filename, file.st_size)
            except Exception as e:  # pylint: disable=broad-except
                current_app.logger.error(e)
                current_app.logger.error(f'upload to minio failed for the file: {file_full_name}')
                raise

    @classmethod
    def _post_process(cls, payment_file_list: List[str]):
        """
        1.Move the file to backup folder
        2.Send a message to queue
        """
        cls.move_file_to_backup(payment_file_list)
        cls.publish_to_queue(payment_file_list)

    @classmethod
    def move_file_to_backup(cls, payment_file_list):
        sftp_client = SFTPService.get_connection()
        ftp_backup_dir: str = current_app.config.get('CAS_SFTP_BACKUP_DIRECTORY')
        ftp_dir: str = current_app.config.get('CAS_SFTP_DIRECTORY')
        for file_name in payment_file_list:
            sftp_client.rename(ftp_dir + '/' + file_name, ftp_backup_dir + '/' + file_name)

    @classmethod
    def _is_valid_payment_file(cls, file_name):
        sftp_client = SFTPService.get_connection()
        return sftp_client.isfile(file_name)

    @classmethod
    def publish_to_queue(cls, file_names_list: List[str]):
        # Publish message to the Queue, saying file has been uploaded. Using the event spec.
        file_names: str = ','.join(file_names_list)
        queue_data = {
            'fileName': file_names,
            'file_source': 'MINIO',
            'location': current_app.config['MINIO_BUCKET_NAME']
        }

        payload = {
            'specversion': '1.x-wip',
            'type': 'bc.registry.payment.' + 'paymentFileTypeUploaded',
            'source': file_names,
            'id': file_names,
            'time': f'{datetime.now()}',
            'datacontenttype': 'application/json',
            'data': queue_data
        }

        try:
            publish_response(payload=payload,
                             client_name=current_app.config.get('NATS_ACCOUNT_CLIENT_NAME'),
                             subject=current_app.config.get('NATS_ACCOUNT_SUBJECT'))
        except Exception as e:  # pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.warning(
                f'Notification to Queue failed for the file '
                f': {",".join(file_names)}',
                e)
            raise
