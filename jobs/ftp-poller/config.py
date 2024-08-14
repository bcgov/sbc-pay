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
"""All of the configuration for the service is captured here. All items are loaded, or have Constants defined here that are loaded into the Flask configuration. All modules and lookups get their configuration from the Flask config, rather than reading environment variables directly or by accessing this configuration directly.
"""

import os
import sys

from dotenv import find_dotenv, load_dotenv

# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    'development': 'config.DevConfig',
    'testing': 'config.TestConfig',
    'production': 'config.ProdConfig',
    'default': 'config.ProdConfig'
}


def get_named_config(config_name: str = 'production'):
    """Return the configuration object based on the name

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ['production', 'staging', 'default']:
        config = ProdConfig()
    elif config_name == 'testing':
        config = TestConfig()
    elif config_name == 'development':
        config = DevConfig()
    else:
        raise KeyError(f"Unknown configuration '{config_name}'")
    return config


class _Config(object):  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults for all the other configurations. """
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

    SECRET_KEY = 'a secret'

    # FTP CONFIG
    CAS_SFTP_HOST = os.getenv('CAS_SFTP_HOST', 'localhost')
    CAS_SFTP_USER_NAME = os.getenv('CAS_SFTP_USER_NAME', 'foo')
    CAS_SFTP_PASSWORD = os.getenv('CAS_SFTP_PASSWORD', '')
    CAS_SFTP_DIRECTORY = os.getenv('CAS_SFTP_DIRECTORY', '/upload')
    CAS_SFTP_BACKUP_DIRECTORY = os.getenv('CAS_SFTP_BACKUP_DIRECTORY', '/backup')
    SFTP_VERIFY_HOST = os.getenv('SFTP_VERIFY_HOST', 'True')
    CAS_SFTP_PORT = os.getenv('CAS_SFTP_PORT', 22)
    CAS_SFTP_HOST_KEY = os.getenv('CAS_SFTP_HOST_KEY', '')
    BCREG_FTP_PRIVATE_KEY_LOCATION = os.getenv('BCREG_FTP_PRIVATE_KEY_LOCATION',
                                               '/ftp-poller/key/sftp_priv_key')  # full path to the privatey key
    BCREG_FTP_PRIVATE_KEY_PASSPHRASE = os.getenv('BCREG_FTP_PRIVATE_KEY_PASSPHRASE', '')

    # CGI FTP CONFIG
    BCREG_CGI_FTP_PRIVATE_KEY_LOCATION = os.getenv('BCREG_CGI_FTP_PRIVATE_KEY_LOCATION',
                                                   '/ftp-poller/key/cgi_sftp_priv_key')  # full path to the privatey key
    BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE = os.getenv('BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE', '')
    CGI_SFTP_USER_NAME = os.getenv('CAS_SFTP_USER_NAME', 'foo')
    CGI_SFTP_BACKUP_DIRECTORY = os.getenv('CGI_SFTP_BACKUP_DIRECTORY', '/backup')
    CGI_SFTP_DIRECTORY = os.getenv('CGI_SFTP_DIRECTORY', '/data')

    # EFT FTP CONFIG
    BCREG_EFT_FTP_PRIVATE_KEY_LOCATION = os.getenv('BCREG_EFT_FTP_PRIVATE_KEY_LOCATION',
                                                   '/ftp-poller/key/eft_sftp_priv_key')
    EFT_SFTP_HOST = os.getenv('EFT_SFTP_HOST', 'localhost')
    EFT_SFTP_USER_NAME = os.getenv('EFT_SFTP_USER_NAME', 'foo')
    EFT_SFTP_PASSWORD = os.getenv('EFT_SFTP_PASSWORD', '')
    EFT_SFTP_DIRECTORY = os.getenv('EFT_SFTP_DIRECTORY', '/outgoing')
    EFT_SFTP_BACKUP_DIRECTORY = os.getenv('EFT_SFTP_BACKUP_DIRECTORY', '/outgoing-backup')
    EFT_SFTP_VERIFY_HOST = os.getenv('EFT_SFTP_VERIFY_HOST', 'True')
    EFT_SFTP_PORT = os.getenv('EFT_SFTP_PORT', 22)
    EFT_SFTP_HOST_KEY = os.getenv('EFT_SFTP_HOST_KEY', '')
    BCREG_EFT_FTP_PRIVATE_KEY_PASSPHRASE = os.getenv('BCREG_EFT_FTP_PRIVATE_KEY_PASSPHRASE', '')

    # CGI File specific configs
    CGI_TRIGGER_FILE_SUFFIX = os.getenv('CGI_TRIGGER_FILE_SUFFIX', '.TRG')
    CGI_ACK_FILE_PREFIX = os.getenv('CGI_ACK_FILE_PREFIX', 'ACK')
    CGI_FEEDBACK_FILE_PREFIX = os.getenv('CGI_FEEDBACK_FILE_PREFIX', 'FEEDBACK')
    CGI_INBOX_FILE_PREFIX = os.getenv('CGI_FEEDBACK_FILE_PREFIX', 'INBOX')

    SFTP_CONFIGS = {
        'CAS': {
            'SFTP_HOST': CAS_SFTP_HOST,
            'SFTP_USERNAME': CAS_SFTP_USER_NAME,
            'SFTP_PASSWORD': CAS_SFTP_PASSWORD,
            'SFTP_VERIFY_HOST': SFTP_VERIFY_HOST,
            'SFTP_HOST_KEY': CAS_SFTP_HOST_KEY,
            'SFTP_PORT': CAS_SFTP_PORT,
            'FTP_PRIVATE_KEY_LOCATION': BCREG_FTP_PRIVATE_KEY_LOCATION,
            'BCREG_FTP_PRIVATE_KEY_PASSPHRASE': BCREG_FTP_PRIVATE_KEY_PASSPHRASE
        },
        # between CGI and CAS , only account name and private key changes.So reusing most of the information.
        'CGI': {
            'SFTP_HOST': os.getenv('CAS_SFTP_HOST', 'localhost'),  # same as CAS
            'SFTP_USERNAME': os.getenv('CGI_SFTP_USER_NAME', 'foo'),  # different user.so not same as CAS
            'SFTP_PASSWORD': os.getenv('CAS_SFTP_PASSWORD', ''),  # same as CAS
            'SFTP_VERIFY_HOST': os.getenv('SFTP_VERIFY_HOST', 'True'),  # same as CAS
            'SFTP_HOST_KEY': os.getenv('CAS_SFTP_HOST_KEY', ''),  # same as CAS
            'SFTP_PORT': CAS_SFTP_PORT,  # same as CAS
            'FTP_PRIVATE_KEY_LOCATION': BCREG_CGI_FTP_PRIVATE_KEY_LOCATION,  # different user.so not same as CAS
            'BCREG_FTP_PRIVATE_KEY_PASSPHRASE': BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE
        },
        'EFT': {
            'SFTP_HOST': EFT_SFTP_HOST,
            'SFTP_USERNAME': EFT_SFTP_USER_NAME,
            'SFTP_PASSWORD': EFT_SFTP_PASSWORD,
            'SFTP_VERIFY_HOST': EFT_SFTP_VERIFY_HOST,
            'SFTP_HOST_KEY': EFT_SFTP_HOST_KEY,
            'SFTP_PORT': EFT_SFTP_PORT,
            'FTP_PRIVATE_KEY_LOCATION': BCREG_FTP_PRIVATE_KEY_LOCATION,
            'BCREG_FTP_PRIVATE_KEY_PASSPHRASE': BCREG_EFT_FTP_PRIVATE_KEY_PASSPHRASE
        }
    }

    # Minio configuration values
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_ACCESS_SECRET = os.getenv('MINIO_ACCESS_SECRET')
    MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'payment-sftp')
    MINIO_CGI_BUCKET_NAME = os.getenv('MINIO_CGI_BUCKET_NAME', 'cgi-ejv')
    MINIO_EFT_BUCKET_NAME = os.getenv('MINIO_EFT_BUCKET_NAME', 'eft-sftp')
    MINIO_SECURE = True

    SENTRY_ENABLE = os.getenv('SENTRY_ENABLE', 'False')
    SENTRY_DSN = os.getenv('SENTRY_DSN', None)

    # PUB/SUB - PUB: ftp-poller-payment-reconciliation-dev
    FTP_POLLER_TOPIC = os.getenv('FTP_POLLER_TOPIC', 'ftp-poller-payment-reconciliation-dev')
    GCP_AUTH_KEY = os.getenv('AUTHPAY_GCP_AUTH_KEY', None)
    PUB_ENABLE_MESSAGE_ORDERING = os.getenv('PUB_ENABLE_MESSAGE_ORDERING', 'True')

    TESTING = False
    DEBUG = True


class DevConfig(_Config):  # pylint: disable=too-few-public-methods
    TESTING = False
    DEBUG = True


class TestConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only used by the py.test suite."""

    DEBUG = True
    TESTING = True
    # POSTGRESQL

    SERVER_NAME = 'localhost:5001'

    AUTH_API_ENDPOINT = 'http://localhost:8080/auth-api/'

    CFS_BASE_URL = 'http://localhost:8080/paybc-api'
    CFS_CLIENT_ID = 'TEST'
    CFS_CLIENT_SECRET = 'TEST'
    USE_DOCKER_MOCK = os.getenv('USE_DOCKER_MOCK', None)

    CAS_SFTP_HOST = 'localhost'
    CAS_SFTP_USER_NAME = 'ftp_user'
    CAS_SFTP_PASSWORD = 'ftp_pass'
    CAS_SFTP_DIRECTORY = 'paymentfolder'
    CAS_SFTP_BACKUP_DIRECTORY = 'backup'
    SFTP_VERIFY_HOST = 'False'
    CAS_SFTP_PORT = 2222

    SFTP_CONFIGS = {
        'CAS': {
            'SFTP_HOST': CAS_SFTP_HOST,
            'SFTP_USERNAME': CAS_SFTP_USER_NAME,
            'SFTP_PASSWORD': CAS_SFTP_PASSWORD,
            'SFTP_VERIFY_HOST': SFTP_VERIFY_HOST,
            'SFTP_PORT': CAS_SFTP_PORT
        }
    }


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = os.getenv('SECRET_KEY', None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False
