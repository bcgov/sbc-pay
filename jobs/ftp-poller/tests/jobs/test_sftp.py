# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests to assure the CreateAccountTask.

Test-Suite to ensure that the CreateAccountTask is working as expected.
"""
import pytest
from flask import current_app
from sbc_common_components.utils.enums import QueueMessageTypes

from services.sftp import SFTPService
from utils.utils import publish_to_queue


def test_cget_sftp_connection():
    """Test create account."""
    con = SFTPService.get_connection()
    assert con


def test_poll_ftp_task():
    """Test Poll."""
    con = SFTPService.get_connection()

    ftp_dir: str = current_app.config.get("CAS_SFTP_DIRECTORY")
    files = con.listdir(ftp_dir)
    assert len(files) == 1, "Files exist in FTP folder"


@pytest.mark.skip(
    reason="leave this to manually verify pubsub connection;"
    "needs env vars, disable def mock_queue_publish(monkeypatch):"
)
def test_queue_message(session):  # pylint:disable=unused-argument
    """Test publishing to topic."""
    file_name = "file1.csv"
    publish_to_queue([file_name])
    publish_to_queue([file_name], QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)
    publish_to_queue(
        [file_name],
        QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value,
        location=current_app.config.get("MINIO_CGI_BUCKET_NAME"),
    )
    publish_to_queue(
        [file_name], QueueMessageTypes.EFT_FILE_UPLOADED.value, location=current_app.config.get("MINIO_EFT_BUCKET_NAME")
    )
