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
    CAS_SFTP_PASSWORD = os.getenv('CAS_SFTP_PASSWORD', 'pass')
    CAS_SFTP_DIRECTORY = os.getenv('CAS_SFTP_DIRECTORY', '/upload')
    CAS_SFTP_BACKUP_DIRECTORY = os.getenv('CAS_SFTP_BACKUP_DIRECTORY', '/backup')
    SFTP_VERIFY_HOST = os.getenv('SFTP_VERIFY_HOST', 'True')
    CAS_SFTP_PORT = os.getenv('CAS_SFTP_PORT', 22)

    # NATS Config
    NATS_SERVERS = os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(',')
    NATS_CLUSTER_ID = os.getenv('NATS_CLUSTER_ID', 'test-cluster')
    NATS_QUEUE = os.getenv('NATS_QUEUE', 'account-worker')

    # NATS Config for account events
    NATS_ACCOUNT_CLIENT_NAME = os.getenv('NATS_CLIENT_NAME', 'account.events.worker')
    NATS_ACCOUNT_SUBJECT = os.getenv('NATS_SUBJECT', 'account.events')

    # Minio configuration values
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_ACCESS_SECRET = os.getenv('MINIO_ACCESS_SECRET')
    MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'payment-sftp')
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


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = os.getenv('SECRET_KEY', None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False
