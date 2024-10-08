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
"""Utility functions for sFTP."""
from base64 import decodebytes

import paramiko
from flask import current_app
from pysftp import CnOpts, Connection


def upload_to_ftp(local_file_path: str, trg_file_path: str):
    """Upload files to sftp."""
    config = current_app.config
    sftp_host: str = config.get("CGI_SFTP_HOST")
    cnopts = CnOpts()
    # only for local development set this to false .
    if config.get("CGI_SFTP_VERIFY_HOST").lower() == "false":
        cnopts.hostkeys = None
    else:
        ftp_host_key_data = config.get("CGI_SFTP_HOST_KEY").encode()
        key = paramiko.RSAKey(data=decodebytes(ftp_host_key_data))
        cnopts.hostkeys.add(sftp_host, "ssh-rsa", key)

    sftp_port: int = config.get("CGI_SFTP_PORT")
    sftp_credentials = {
        "username": config.get("CGI_SFTP_USERNAME"),
        # private_key should be the absolute path to where private key file lies since sftp
        "private_key": config.get("BCREG_CGI_FTP_PRIVATE_KEY_LOCATION"),
        "private_key_pass": config.get("BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE"),
    }

    # to support local testing. SFTP CAS server should run in private key mode
    if password := config.get("CGI_SFTP_PASSWORD"):
        sftp_credentials["password"] = password

    with Connection(host=sftp_host, **sftp_credentials, cnopts=cnopts, port=sftp_port) as sftp_connection:
        current_app.logger.debug("sftp_connection successful")
        with sftp_connection.cd(config.get("CGI_SFTP_DIRECTORY")):
            sftp_connection.put(local_file_path)
            # Now upload trg file
            sftp_connection.put(trg_file_path)
        sftp_connection.close()
    current_app.logger.debug("File upload complete")
