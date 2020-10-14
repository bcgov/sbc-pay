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

    # PAYBC Direct Pay Settings
    PAYBC_DIRECT_PAY_REF_NUMBER = os.getenv('PAYBC_DIRECT_PAY_REF_NUMBER')
    PAYBC_DIRECT_PAY_API_KEY = os.getenv('PAYBC_DIRECT_PAY_API_KEY')
    PAYBC_DIRECT_PAY_BASE_URL = os.getenv('PAYBC_DIRECT_PAY_BASE_URL')
    PAYBC_DIRECT_PAY_CLIENT_ID = os.getenv('PAYBC_DIRECT_PAY_CLIENT_ID')
    PAYBC_DIRECT_PAY_CLIENT_SECRET = os.getenv('PAYBC_DIRECT_PAY_CLIENT_SECRET')

    # CFS API Settings
    CFS_BASE_URL = os.getenv('CFS_BASE_URL')
    CFS_CLIENT_ID = os.getenv('CFS_CLIENT_ID')
    CFS_CLIENT_SECRET = os.getenv('CFS_CLIENT_SECRET')
    CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', default=10))
    GENERATE_RANDOM_INVOICE_NUMBER = os.getenv('CFS_GENERATE_RANDOM_INVOICE_NUMBER', default='False')

    # legislative timezone for future effective dating
    LEGISLATIVE_TIMEZONE = os.getenv('LEGISLATIVE_TIMEZONE', 'America/Vancouver')

    # notify-API URL
    NOTIFY_API_URL = os.getenv('NOTIFY_API_URL')

    # Service account details
    KEYCLOAK_SERVICE_ACCOUNT_ID = os.getenv('KEYCLOAK_SERVICE_ACCOUNT_ID')
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = os.getenv('KEYCLOAK_SERVICE_ACCOUNT_SECRET')

    # JWT_OIDC Settings
    JWT_OIDC_ISSUER = os.getenv('JWT_OIDC_ISSUER')

    # Front end url
    AUTH_WEB_URL = os.getenv('AUTH_WEB_PAY_TRANSACTION_URL', '')
    AUTH_WEB_STATEMENT_URL = os.getenv('AUTH_WEB_STATEMENT_URL', 'account/orgId/settings/statements')
    REGISTRIES_LOGO_IMAGE_NAME = os.getenv('REGISTRIES_LOGO_IMAGE_NAME', 'bc_logo_for_email.png')

    TESTING = False
    DEBUG = True

    # NATS Config
    NATS_SERVERS = os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(',')
    NATS_CLIENT_NAME = os.getenv('NATS_CLIENT_NAME', 'entity.filing.worker')
    NATS_CLUSTER_ID = os.getenv('NATS_CLUSTER_ID', 'test-cluster')
    NATS_SUBJECT = os.getenv('NATS_SUBJECT', 'entity.filings')
    NATS_QUEUE = os.getenv('NATS_QUEUE', 'filing-worker')


class DevConfig(_Config):  # pylint: disable=too-few-public-methods
    TESTING = False
    DEBUG = True


class TestConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only used by the py.test suite."""
    DEBUG = True
    TESTING = True
    # POSTGRESQL
    DB_USER = os.getenv('DATABASE_TEST_USERNAME', '')
    DB_PASSWORD = os.getenv('DATABASE_TEST_PASSWORD', '')
    DB_NAME = os.getenv('DATABASE_TEST_NAME', '')
    DB_HOST = os.getenv('DATABASE_TEST_HOST', '')
    DB_PORT = os.getenv('DATABASE_TEST_PORT', '5432')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_TEST_URL',
                                        'postgresql://{user}:{password}@{host}:{port}/{name}'.format(
                                            user=DB_USER,
                                            password=DB_PASSWORD,
                                            host=DB_HOST,
                                            port=int(DB_PORT),
                                            name=DB_NAME,
                                        ))

    SERVER_NAME = 'localhost:5001'


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = os.getenv('SECRET_KEY', None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False
