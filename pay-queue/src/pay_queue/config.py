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
"""All of the configuration for the service is captured here.

All items are loaded, or have Constants defined here that
are loaded into the Flask configuration.
All modules and lookups get their configuration from the
Flask config, rather than reading environment variables directly
or by accessing this configuration directly.
"""
import os

from dotenv import find_dotenv, load_dotenv


# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    'development': 'pay_queue.config.DevConfig',
    'testing': 'pay_queue.config.TestConfig',
    'production': 'pay_queue.config.ProdConfig',
    'default': 'pay_queue.config.ProdConfig'
}


def get_named_config(config_name: str = 'production'):
    """Return the configuration object based on the name.

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ['production', 'staging', 'default']:
        app_config = ProdConfig()
    elif config_name == 'testing':
        app_config = TestConfig()
    elif config_name == 'development':
        app_config = DevConfig()
    else:
        raise KeyError(f'Unknown configuration: {config_name}')
    return app_config


class _Config():  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults.

    Used as the base for all the other configurations.
    """

    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
    PAY_LD_SDK_KEY = os.getenv('PAY_LD_SDK_KEY', None)
    LEGISLATIVE_TIMEZONE = os.getenv('LEGISLATIVE_TIMEZONE', 'America/Vancouver')

    SENTRY_ENABLE = os.getenv('SENTRY_ENABLE', 'False')
    SENTRY_DSN = os.getenv('SENTRY_DSN', None)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_USERNAME', '')
    DB_PASSWORD = os.getenv('DATABASE_PASSWORD', '')
    DB_NAME = os.getenv('DATABASE_NAME', '')
    DB_HOST = os.getenv('DATABASE_HOST', '')
    DB_PORT = os.getenv('DATABASE_PORT', '5432')
    if DB_UNIX_SOCKET := os.getenv('DATABASE_UNIX_SOCKET', None):
        SQLALCHEMY_DATABASE_URI = (
            f'postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?unix_sock={DB_UNIX_SOCKET}/.s.PGSQL.5432'
        )
    else:
        SQLALCHEMY_DATABASE_URI = f'postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'

    # Minio configuration values
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_ACCESS_SECRET = os.getenv('MINIO_ACCESS_SECRET')
    MINIO_SECURE = os.getenv('MINIO_SECURE', 'True').lower() == 'true'

    # CFS API Settings
    CFS_BASE_URL = os.getenv('CFS_BASE_URL')
    CFS_CLIENT_ID = os.getenv('CFS_CLIENT_ID')
    CFS_CLIENT_SECRET = os.getenv('CFS_CLIENT_SECRET')
    CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', '10'))

    # EFT Config
    EFT_INVOICE_PREFIX = os.getenv('EFT_INVOICE_PREFIX', 'REG')

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY')

    # Disable EJV Error Email
    DISABLE_EJV_ERROR_EMAIL = os.getenv('DISABLE_EJV_ERROR_EMAIL', 'true').lower() == 'true'
    # Disable PAD Success Email - Incase we need to reprocess records weeks/months later
    DISABLE_PAD_SUCCESS_EMAIL = os.getenv('DISABLE_PAD_SUCCESS_EMAIL', 'false').lower() == 'true'

    # GCP PubSub
    AUDIENCE = os.getenv('AUDIENCE', None)
    GCP_AUTH_KEY = os.getenv('GCP_AUTH_KEY', None)
    PUBLISHER_AUDIENCE = os.getenv('PUBLISHER_AUDIENCE', None)
    ACCOUNT_MAILER_TOPIC = os.getenv('ACCOUNT_MAILER_TOPIC', None)


class DevConfig(_Config):  # pylint: disable=too-few-public-methods
    """Creates the Development Config object."""

    TESTING = False
    DEBUG = True


class TestConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only.

    Used by the py.test suite
    """

    DEBUG = True
    TESTING = True
    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_TEST_USERNAME', '')
    DB_PASSWORD = os.getenv('DATABASE_TEST_PASSWORD', '')
    DB_NAME = os.getenv('DATABASE_TEST_NAME', '')
    DB_HOST = os.getenv('DATABASE_TEST_HOST', '')
    DB_PORT = os.getenv('DATABASE_TEST_PORT', '5432')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_TEST_URL',
        default=f'postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'
    )

    USE_DOCKER_MOCK = os.getenv('USE_DOCKER_MOCK', None)

    # Minio variables
    MINIO_ENDPOINT = 'localhost:9000'
    MINIO_ACCESS_KEY = 'minio'
    MINIO_ACCESS_SECRET = 'minio123'
    MINIO_BUCKET_NAME = 'payment-sftp'
    MINIO_SECURE = False

    CFS_BASE_URL = 'http://localhost:8080/paybc-api'
    CFS_CLIENT_ID = 'TEST'
    CFS_CLIENT_SECRET = 'TEST'

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY', 'test')

    # Secrets for integration tests
    TEST_GCP_PROJECT_NAME = 'abdefg-dev'
    # Needs to have ftp-poller-dev in it.
    TEST_GCP_TOPICS = ['account-mailer-dev', 'ftp-poller-dev', 'business-identifier-update-pay-dev']
    TEST_PUSH_ENDPOINT_PORT = 5020
    TEST_PUSH_ENDPOINT = f'http://host.docker.internal:{str(TEST_PUSH_ENDPOINT_PORT)}/'


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    TESTING = False
    DEBUG = False
