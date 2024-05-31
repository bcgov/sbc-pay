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
from paramiko import SFTPFile
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.enums import MessageType, QueueSources

from utils.minio import put_object


def publish_to_queue(payment_file_list: List[str], message_type=MessageType.CAS_UPLOADED.value, location: str = ''):
    """Publish message to the Queue, saying file has been uploaded. Using the event spec."""
    queue_data = {
        'fileSource': 'MINIO',
        'location': location or current_app.config['MINIO_BUCKET_NAME']
    }
    for file_name in payment_file_list:
        queue_data['fileName'] = file_name

        try:
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.FTP_POLLER.value,
                    message_type=message_type,
                    payload=queue_data,
                    topic=current_app.config.get('FTP_POLLER_TOPIC')
                )
            )
        except Exception as e:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.warning(
                f'Notification to Queue failed for the file {file_name}',
                e)
            raise


def upload_to_minio(file, file_full_name, sftp_client, bucket_name):
    """Upload to minio."""
    f: SFTPFile
    with sftp_client.open(file_full_name) as f:
        f.prefetch()
        value_as_bytes = f.read()
        try:
            put_object(value_as_bytes, file.filename, bucket_name, file.st_size, )
        except Exception as e:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.error(f'upload to minio failed for the file: {file_full_name}')
            raise
