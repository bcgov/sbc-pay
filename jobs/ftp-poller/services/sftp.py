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
"""This module is a wrapper for SFTP Connection object."""
from base64 import decodebytes

import paramiko
from flask import current_app
from pysftp import Connection, CnOpts


class SFTPService:  # pylint: disable=too-few-public-methods
    """SFTP  Service class."""

    __instance: Connection = None

    @staticmethod
    def get_connection() -> Connection:
        """Return a SFTP connection."""
        # pylint: disable=protected-access
        if not SFTPService.__instance or not SFTPService.__instance._sftp_live:
            SFTPService.__instance = SFTPService._connect()
        return SFTPService.__instance

    @staticmethod
    def _connect() -> Connection:

        sftp_host: str = current_app.config.get('CAS_SFTP_HOST')
        cnopts = CnOpts()
        # only for local development set this to false .
        if current_app.config.get('SFTP_VERIFY_HOST').lower() == 'false':
            cnopts.hostkeys = None
        else:
            ftp_host_key_data = current_app.config.get('CAS_SFTP_HOST_KEY')
            key = paramiko.RSAKey(data=decodebytes(ftp_host_key_data))
            cnopts.hostkeys.add(sftp_host, 'ssh-rsa', key)

        sftp_port: int = current_app.config.get('CAS_SFTP_PORT')
        sft_credentials = {
            'username': current_app.config.get('CAS_SFTP_USER_NAME'),
            'password': current_app.config.get('CAS_SFTP_PASSWORD'),
            'private_key': current_app.config.get('BCREG_FTP_PRIVATE_KEY'),
            'private_key_pass': current_app.config.get('BCREG_FTP_PRIVATE_KEY_PASSPHRASE')
        }
        sftp_connection = Connection(host=sftp_host, **sft_credentials, cnopts=cnopts, port=sftp_port)
        return sftp_connection
