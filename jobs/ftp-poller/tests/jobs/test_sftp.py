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

from services.sftp import SFTPService
from utils.utils import publish_to_queue


def test_cget_sftp_connection():
    """Test create account."""
    con = SFTPService.get_connection()
    assert con


def test_poll_ftp_task():
    """Test Poll."""
    con = SFTPService.get_connection()

    ftp_dir: str = current_app.config.get('CAS_SFTP_DIRECTORY')
    files = con.listdir(ftp_dir)
    assert len(files) == 1, 'Files exist in FTP folder'


@pytest.mark.skip(reason='leave this to manually verify pubsub connection; needs env vars')
def test_queue_message():
    """Test publishing to topic."""
    publish_to_queue(['file1.csv'])
