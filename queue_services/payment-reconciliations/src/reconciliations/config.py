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
import random

from dotenv import find_dotenv, load_dotenv


# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    'development': 'reconciliations.config.DevConfig',
    'testing': 'reconciliations.config.TestConfig',
    'production': 'reconciliations.config.ProdConfig',
    'default': 'reconciliations.config.ProdConfig'
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

    SENTRY_ENABLE = os.getenv('SENTRY_ENABLE', 'False')
    SENTRY_DSN = os.getenv('SENTRY_DSN', None)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_USERNAME', '')
    DB_PASSWORD = os.getenv('DATABASE_PASSWORD', '')
    DB_NAME = os.getenv('DATABASE_NAME', '')
    DB_HOST = os.getenv('DATABASE_HOST', '')
    DB_PORT = os.getenv('DATABASE_PORT', '5432')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'
    NATS_CONNECTION_OPTIONS = {
        'servers': os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(','),
        'name': os.getenv('NATS_PAYMENT_RECONCILIATIONS_CLIENT_NAME', 'payment.reconciliations.worker')

    }
    STAN_CONNECTION_OPTIONS = {
        'cluster_id': os.getenv('NATS_CLUSTER_ID', 'test-cluster'),
        'client_id': str(random.SystemRandom().getrandbits(0x58)),
        'ping_interval': 1,
        'ping_max_out': 5,
    }

    SUBSCRIPTION_OPTIONS = {
        'subject': os.getenv('NATS_PAYMENT_RECONCILIATIONS_SUBJECT', 'payment.reconciliations'),
        'queue': os.getenv('NATS_PAYMENT_RECONCILIATIONS_QUEUE', 'payment-reconciliations-worker'),
        'durable_name': os.getenv('NATS_PAYMENT_RECONCILIATIONS_QUEUE', 'payment-reconciliations-worker') + '_durable',
    }

    # Minio configuration values
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_ACCESS_SECRET = os.getenv('MINIO_ACCESS_SECRET')
    MINIO_SECURE = os.getenv('MINIO_SECURE', 'True').lower() == 'true'

    # NATS Config
    NATS_SERVERS = os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(',')
    NATS_CLUSTER_ID = os.getenv('NATS_CLUSTER_ID', 'test-cluster')
    NATS_PAYMENT_CLIENT_NAME = os.getenv('NATS_PAYMENT_CLIENT_NAME', 'entity.filing.worker')
    NATS_PAYMENT_SUBJECT = os.getenv('NATS_PAYMENT_SUBJECT', 'entity.{product}.payment')
    NATS_MAILER_CLIENT_NAME = os.getenv('NATS_MAILER_CLIENT_NAME', 'account.mailer.worker')
    NATS_MAILER_SUBJECT = os.getenv('NATS_MAILER_SUBJECT', 'account.mailer')
    NATS_ACCOUNT_CLIENT_NAME = os.getenv('NATS_ACCOUNT_CLIENT_NAME', 'account.events.worker')
    NATS_ACCOUNT_SUBJECT = os.getenv('NATS_ACCOUNT_SUBJECT', 'account.events')

    # CFS API Settings
    CFS_BASE_URL = os.getenv('CFS_BASE_URL')
    CFS_CLIENT_ID = os.getenv('CFS_CLIENT_ID')
    CFS_CLIENT_SECRET = os.getenv('CFS_CLIENT_SECRET')
    CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', '10'))

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY')

    # Disable EJV Error Email
    DISABLE_EJV_ERROR_EMAIL = os.getenv('DISABLE_EJV_ERROR_EMAIL', 'true').lower() == 'true'
    # Disable PAD Success Email - Incase we need to reprocess records weeks/months later
    DISABLE_PAD_SUCCESS_EMAIL = os.getenv('DISABLE_PAD_SUCCESS_EMAIL', 'false').lower() == 'true'


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
        default=f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'
    )

    TEST_NATS_DOCKER = os.getenv('TEST_NATS_DOCKER', None)
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

    # NATS Config
    NATS_SERVERS = os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(',')
    NATS_CLUSTER_ID = os.getenv('NATS_CLUSTER_ID', 'test-cluster')
    NATS_PAYMENT_CLIENT_NAME = os.getenv('NATS_PAYMENT_CLIENT_NAME', 'entity.filing.worker')
    NATS_PAYMENT_SUBJECT = os.getenv('NATS_PAYMENT_SUBJECT', 'entity.{product}.payment')
    NATS_MAILER_CLIENT_NAME = os.getenv('NATS_MAILER_CLIENT_NAME', 'account.mailer.worker')
    NATS_MAILER_SUBJECT = os.getenv('NATS_MAILER_SUBJECT', 'account.mailer')
    NATS_ACCOUNT_CLIENT_NAME = os.getenv('NATS_ACCOUNT_CLIENT_NAME', 'account.events.worker')
    NATS_ACCOUNT_SUBJECT = os.getenv('NATS_ACCOUNT_SUBJECT', 'account.events')

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY', 'test')


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    TESTING = False
    DEBUG = False
