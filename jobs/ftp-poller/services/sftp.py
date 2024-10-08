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
import json
from base64 import decodebytes
from typing import Dict

import paramiko
from flask import current_app
from pysftp import CnOpts, Connection


class SFTPService:  # pylint: disable=too-few-public-methods
    """SFTP  Service class."""

    DEFAULT_CONNECT_SERVER = "CAS"

    @staticmethod
    def get_connection(server_name: str = DEFAULT_CONNECT_SERVER) -> Connection:
        """Return a SFTP connection."""
        # pylint: disable=protected-access
        return SFTPService._connect(server_name)

    @staticmethod
    def _connect(server_name: str) -> Connection:

        sftp_configs = current_app.config.get("SFTP_CONFIGS")
        # if not passed , connect to CAS server always. to make the existing code work
        if not server_name or server_name not in sftp_configs.keys():
            server_name = SFTPService.DEFAULT_CONNECT_SERVER

        connect_configs = sftp_configs.get(server_name)

        sftp_host: str = connect_configs.get("SFTP_HOST")
        cnopts = CnOpts()
        # only for local development set this to false .
        if connect_configs.get("SFTP_VERIFY_HOST").lower() == "false":
            cnopts.hostkeys = None
        else:
            ftp_host_key_data = connect_configs.get("SFTP_HOST_KEY").encode()
            key = paramiko.RSAKey(data=decodebytes(ftp_host_key_data))
            cnopts.hostkeys.add(sftp_host, "ssh-rsa", key)

        sftp_port: int = connect_configs.get("SFTP_PORT")
        sft_credentials = {
            "username": connect_configs.get("SFTP_USERNAME"),
            # private_key should be the absolute path to where private key file lies since sftp
            "private_key": connect_configs.get("FTP_PRIVATE_KEY_LOCATION"),
            "private_key_pass": connect_configs.get("BCREG_FTP_PRIVATE_KEY_PASSPHRASE"),
        }

        # to support local testing. SFTP CAS server should run in private key mode
        if password := connect_configs.get("SFTP_PASSWORD"):
            sft_credentials["password"] = password

        sftp_connection = Connection(host=sftp_host, **sft_credentials, cnopts=cnopts, port=sftp_port)
        current_app.logger.debug("sftp_connection successful")
        return sftp_connection
