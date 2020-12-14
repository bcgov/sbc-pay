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
# import os
# from typing import List

from flask import current_app

from services.sftp import SFTPService
# from utils.minio import get_object
# from tasks.poll_ftp_task import PollFtpTask


def test_cget_sftp_connection(session):  # pylint:disable=unused-argument
    """Test create account."""
    con = SFTPService.get_connection()
    assert con


def test_poll_ftp_task(session):    # pylint:disable=unused-argument
    """Test Poll."""
    con = SFTPService.get_connection()

    ftp_dir: str = current_app.config.get('CAS_SFTP_DIRECTORY')
    files = con.listdir(ftp_dir)
    assert len(files) == 1, 'Files exist in FTP folder'

    # TODO fixed this test case
    # payment_file_list: List[str] = PollFtpTask.poll_ftp()
    # minio_file_content = get_object(payment_file_list[0]).read().decode()
    # full_path = os.path.join(os.path.dirname(__file__), '../docker/ftp/test.txt')
    # sftp_local_file_content = open(full_path, 'r').read()
    # assert minio_file_content == sftp_local_file_content, 'minio upload works fine.' \
    #                                                      'Contents of ftp drive and minio verified'
