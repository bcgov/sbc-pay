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

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALEMBIC_INI = 'migrations/alembic.ini'

    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_USERNAME', '')
    DB_PASSWORD = os.getenv('DATABASE_PASSWORD', '')
    DB_NAME = os.getenv('DATABASE_NAME', '')
    DB_HOST = os.getenv('DATABASE_HOST', '')
    DB_PORT = os.getenv('DATABASE_PORT', '5432')

    SQLALCHEMY_DATABASE_URI = 'postgresql://{user}:{password}@{host}:{port}/{name}'.format(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        name=DB_NAME,
    )
    SQLALCHEMY_ECHO = False

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

    # CGI File specific configs
    CGI_TRIGGER_FILE_SUFFIX = os.getenv('CGI_TRIGGER_FILE_SUFFIX', '.TRG')
    CGI_ACK_FILE_PREFIX = os.getenv('CGI_ACK_FILE_PREFIX', 'ACK')
    CGI_FEEDBACK_FILE_PREFIX = os.getenv('CGI_FEEDBACK_FILE_PREFIX', 'FEEDBACK')
    CGI_INBOX_FILE_PREFIX = os.getenv('CGI_FEEDBACK_FILE_PREFIX', 'INBOX')

    # NATS Config
    NATS_SERVERS = os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(',')
    NATS_CLUSTER_ID = os.getenv('NATS_CLUSTER_ID', 'test-cluster')
    NATS_QUEUE = os.getenv('NATS_QUEUE', 'account-worker')

    # NATS Config for account events
    NATS_PAYMENT_RECONCILIATIONS_CLIENT_NAME = os.getenv('NATS_PAYMENT_RECONCILIATIONS_CLIENT_NAME',
                                                         'payment.reconciliations.worker')
    NATS_PAYMENT_RECONCILIATIONS_SUBJECT = os.getenv('NATS_SUBJECT', 'payment.reconciliations')

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
        }
    }

    # Minio configuration values
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_ACCESS_SECRET = os.getenv('MINIO_ACCESS_SECRET')
    MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'payment-sftp')
    MINIO_CGI_BUCKET_NAME = os.getenv('MINIO_CGI_BUCKET_NAME', 'cgi-ejv')
    MINIO_SECURE = True

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

    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_TEST_USERNAME', default='postgres')
    DB_PASSWORD = os.getenv('DATABASE_TEST_PASSWORD', default='postgres')
    DB_NAME = os.getenv('DATABASE_TEST_NAME', default='paytestdb')
    DB_HOST = os.getenv('DATABASE_TEST_HOST', default='localhost')
    DB_PORT = os.getenv('DATABASE_TEST_PORT', default='5432')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_TEST_URL',
        default='postgresql://{user}:{password}@{host}:{port}/{name}'.format(
            user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=int(DB_PORT), name=DB_NAME
        ),
    )


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = os.getenv('SECRET_KEY', None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False
