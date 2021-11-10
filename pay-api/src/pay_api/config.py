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
"""All of the configuration for the service is captured here.

All items are loaded,
or have Constants defined here that are loaded into the Flask configuration.
All modules and lookups get their configuration from the Flask config,
rather than reading environment variables directly or by accessing this configuration directly.
"""

import os
import sys

from dotenv import find_dotenv, load_dotenv


# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    'development': 'pay_api.config.DevConfig',
    'testing': 'pay_api.config.TestConfig',
    'production': 'pay_api.config.ProdConfig',
    'default': 'pay_api.config.ProdConfig',
    'migration': 'pay_api.config.MigrationConfig',
}


def get_named_config(config_name: str = 'production'):
    """Return the configuration object based on the name.

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ['production', 'staging', 'default']:
        config = ProdConfig()
    elif config_name == 'testing':
        config = TestConfig()
    elif config_name == 'development':
        config = DevConfig()
    elif config_name == 'migration':
        config = MigrationConfig()
    else:
        raise KeyError(f"Unknown configuration '{config_name}'")
    return config


def _get_config(config_key: str, **kwargs):
    """Get the config from environment, and throw error if there are no default values and if the value is None."""
    if 'default' in kwargs:
        value = os.getenv(config_key, kwargs.get('default'))
    else:
        value = os.getenv(config_key)
        # assert value TODO Un-comment once we find a solution to run pre-hook without initializing app
    return value


class _Config():  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults for all the other configurations."""

    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

    SECRET_KEY = 'a secret'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALEMBIC_INI = 'migrations/alembic.ini'

    # POSTGRESQL
    DB_USER = _get_config('DATABASE_USERNAME')
    DB_PASSWORD = _get_config('DATABASE_PASSWORD')
    DB_NAME = _get_config('DATABASE_NAME')
    DB_HOST = _get_config('DATABASE_HOST')
    DB_PORT = _get_config('DATABASE_PORT', default='5432')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'
    SQLALCHEMY_ECHO = _get_config('SQLALCHEMY_ECHO', default='False').lower() == 'true'

    # JWT_OIDC Settings
    JWT_OIDC_WELL_KNOWN_CONFIG = _get_config('JWT_OIDC_WELL_KNOWN_CONFIG')
    JWT_OIDC_ALGORITHMS = _get_config('JWT_OIDC_ALGORITHMS')
    JWT_OIDC_JWKS_URI = _get_config('JWT_OIDC_JWKS_URI', default=None)
    JWT_OIDC_ISSUER = _get_config('JWT_OIDC_ISSUER')
    JWT_OIDC_AUDIENCE = _get_config('JWT_OIDC_AUDIENCE')
    JWT_OIDC_CLIENT_SECRET = _get_config('JWT_OIDC_CLIENT_SECRET')
    JWT_OIDC_CACHING_ENABLED = _get_config('JWT_OIDC_CACHING_ENABLED', default=False)
    JWT_OIDC_JWKS_CACHE_TIMEOUT = int(_get_config('JWT_OIDC_JWKS_CACHE_TIMEOUT', default=300))

    # CFS API Settings
    CFS_BASE_URL = _get_config('CFS_BASE_URL')
    CFS_CLIENT_ID = _get_config('CFS_CLIENT_ID')
    CFS_CLIENT_SECRET = _get_config('CFS_CLIENT_SECRET')
    PAYBC_PORTAL_URL = _get_config('PAYBC_PORTAL_URL')
    CONNECT_TIMEOUT = int(_get_config('CONNECT_TIMEOUT', default=10))
    GENERATE_RANDOM_INVOICE_NUMBER = _get_config('CFS_GENERATE_RANDOM_INVOICE_NUMBER', default='False')
    CFS_ACCOUNT_DESCRIPTION = _get_config('CFS_ACCOUNT_DESCRIPTION', default='BCR')
    CFS_INVOICE_PREFIX = os.getenv('CFS_INVOICE_PREFIX', 'REG')
    CFS_RECEIPT_PREFIX = os.getenv('CFS_RECEIPT_PREFIX', 'RCPT')
    CFS_PARTY_PREFIX = os.getenv('CFS_PARTY_PREFIX', 'BCR-')

    # PAYBC Direct Pay Settings
    PAYBC_DIRECT_PAY_REF_NUMBER = _get_config('PAYBC_DIRECT_PAY_REF_NUMBER')
    PAYBC_DIRECT_PAY_API_KEY = _get_config('PAYBC_DIRECT_PAY_API_KEY')
    PAYBC_DIRECT_PAY_PORTAL_URL = _get_config('PAYBC_DIRECT_PAY_PORTAL_URL')
    PAYBC_DIRECT_PAY_BASE_URL = _get_config('PAYBC_DIRECT_PAY_BASE_URL')
    PAYBC_DIRECT_PAY_CLIENT_ID = _get_config('PAYBC_DIRECT_PAY_CLIENT_ID')
    PAYBC_DIRECT_PAY_CLIENT_SECRET = _get_config('PAYBC_DIRECT_PAY_CLIENT_SECRET')

    # NATS Config
    NATS_SERVERS = _get_config('NATS_SERVERS', default='nats://127.0.0.1:4222').split(',')
    NATS_CLUSTER_ID = _get_config('NATS_CLUSTER_ID', default='test-cluster')
    NATS_PAYMENT_CLIENT_NAME = _get_config('NATS_PAYMENT_CLIENT_NAME', default='entity.filing.worker')
    NATS_PAYMENT_SUBJECT = _get_config('NATS_PAYMENT_SUBJECT', default='entity.{product}.payment')

    NATS_MAILER_CLIENT_NAME = _get_config('NATS_MAILER_CLIENT_NAME', default='account.mailer.worker')
    NATS_MAILER_SUBJECT = _get_config('NATS_MAILER_SUBJECT', default='account.mailer')

    NATS_ACCOUNT_CLIENT_NAME = os.getenv('NATS_ACCOUNT_CLIENT_NAME', 'account.events.worker')
    NATS_ACCOUNT_SUBJECT = os.getenv('NATS_ACCOUNT_SUBJECT', 'account.events')

    # Auth API Endpoint
    AUTH_API_ENDPOINT = f'{_get_config("AUTH_API_URL")}/'

    # REPORT API Settings
    REPORT_API_BASE_URL = f'{_get_config("REPORT_API_URL")}/reports'

    # BCOL Service
    BCOL_API_ENDPOINT = _get_config('BCOL_API_URL')

    # Sentry Config
    SENTRY_DSN = _get_config('SENTRY_DSN', default=None)

    # Valid Payment redirect URLs
    VALID_REDIRECT_URLS = [(val.strip() if val != '' else None)
                           for val in _get_config('VALID_REDIRECT_URLS', default='').split(',')]

    # Service account details
    KEYCLOAK_SERVICE_ACCOUNT_ID = _get_config('SBC_AUTH_ADMIN_CLIENT_ID')
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = _get_config('SBC_AUTH_ADMIN_CLIENT_SECRET')

    # Default number of transactions to be returned for transaction reporting
    TRANSACTION_REPORT_DEFAULT_TOTAL = int(_get_config('TRANSACTION_REPORT_DEFAULT_TOTAL', default=50))

    # Default number of routing slips to be returned for routing slip search
    ROUTING_SLIP_DEFAULT_TOTAL = int(_get_config('ROUTING_SLIP_DEFAULT_TOTAL', default=50))

    PAD_CONFIRMATION_PERIOD_IN_DAYS = int(_get_config('PAD_CONFIRMATION_PERIOD_IN_DAYS', default=3))

    # legislative timezone for future effective dating
    LEGISLATIVE_TIMEZONE = os.getenv('LEGISLATIVE_TIMEZONE', 'America/Vancouver')

    # BCOL user name for Service account payments
    BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS = os.getenv('BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS',
                                                           'BCROS SERVICE ACCOUNT')

    # The number of characters which can be exposed to admins for a bank account number
    MASK_LEN = int(_get_config('MASK_LEN', default=3))

    # Config value to disable activity logs
    DISABLE_ACTIVITY_LOGS = os.getenv('DISABLE_ACTIVITY_LOGS', 'False').lower() == 'true'

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY')

    HOLIDAYS_LIST = os.getenv('HOLIDAYS_LIST')

    OUTSTANDING_TRANSACTION_DAYS = int(os.getenv('OUTSTANDING_TRANSACTION_DAYS', '10'))

    ALLOW_LEGACY_ROUTING_SLIPS = os.getenv('ALLOW_LEGACY_ROUTING_SLIPS', 'True').lower() == 'true'

    TESTING = False
    DEBUG = True


class DevConfig(_Config):  # pylint: disable=too-few-public-methods
    """Dev config."""

    TESTING = False
    DEBUG = True


class TestConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only used by the py.test suite."""

    DEBUG = True
    TESTING = True

    USE_TEST_KEYCLOAK_DOCKER = _get_config('USE_TEST_KEYCLOAK_DOCKER', default=None)
    USE_DOCKER_MOCK = _get_config('USE_DOCKER_MOCK', default=None)

    # POSTGRESQL
    DB_USER = _get_config('DATABASE_TEST_USERNAME', default='postgres')
    DB_PASSWORD = _get_config('DATABASE_TEST_PASSWORD', default='postgres')
    DB_NAME = _get_config('DATABASE_TEST_NAME', default='paytestdb')
    DB_HOST = _get_config('DATABASE_TEST_HOST', default='localhost')
    DB_PORT = _get_config('DATABASE_TEST_PORT', default='5432')
    SQLALCHEMY_DATABASE_URI = _get_config(
        'DATABASE_TEST_URL',
        default=f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'
    )

    JWT_OIDC_TEST_MODE = True
    # JWT_OIDC_ISSUER = _get_config('JWT_OIDC_TEST_ISSUER')
    JWT_OIDC_TEST_AUDIENCE = _get_config('JWT_OIDC_TEST_AUDIENCE')
    JWT_OIDC_TEST_CLIENT_SECRET = _get_config('JWT_OIDC_TEST_CLIENT_SECRET')
    JWT_OIDC_TEST_ISSUER = _get_config('JWT_OIDC_TEST_ISSUER')
    JWT_OIDC_WELL_KNOWN_CONFIG = _get_config('JWT_OIDC_WELL_KNOWN_CONFIG')
    JWT_OIDC_TEST_ALGORITHMS = _get_config('JWT_OIDC_TEST_ALGORITHMS')
    JWT_OIDC_TEST_JWKS_URI = _get_config('JWT_OIDC_TEST_JWKS_URI', default=None)

    JWT_OIDC_TEST_KEYS = {
        'keys': [
            {
                'kid': 'sbc-auth-web',
                'kty': 'RSA',
                'alg': 'RS256',
                'use': 'sig',
                'n': 'AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-'
                     'TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR',
                'e': 'AQAB'
            }
        ]
    }

    JWT_OIDC_TEST_PRIVATE_KEY_JWKS = {
        'keys': [
            {
                'kid': 'sbc-auth-web',
                'kty': 'RSA',
                'alg': 'RS256',
                'use': 'sig',
                'n': 'AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-'
                     'TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR',
                'e': 'AQAB',
                'd': 'C0G3QGI6OQ6tvbCNYGCqq043YI_8MiBl7C5dqbGZmx1ewdJBhMNJPStuckhskURaDwk4-'
                     '8VBW9SlvcfSJJrnZhgFMjOYSSsBtPGBIMIdM5eSKbenCCjO8Tg0BUh_'
                     'xa3CHST1W4RQ5rFXadZ9AeNtaGcWj2acmXNO3DVETXAX3x0',
                'p': 'APXcusFMQNHjh6KVD_hOUIw87lvK13WkDEeeuqAydai9Ig9JKEAAfV94W6Aftka7tGgE7ulg1vo3eJoLWJ1zvKM',
                'q': 'AOjX3OnPJnk0ZFUQBwhduCweRi37I6DAdLTnhDvcPTrrNWuKPg9uGwHjzFCJgKd8KBaDQ0X1rZTZLTqi3peT43s',
                'dp': 'AN9kBoA5o6_Rl9zeqdsIdWFmv4DB5lEqlEnC7HlAP-3oo3jWFO9KQqArQL1V8w2D4aCd0uJULiC9pCP7aTHvBhc',
                'dq': 'ANtbSY6njfpPploQsF9sU26U0s7MsuLljM1E8uml8bVJE1mNsiu9MgpUvg39jEu9BtM2tDD7Y51AAIEmIQex1nM',
                'qi': 'XLE5O360x-MhsdFXx8Vwz4304-MJg-oGSJXCK_ZWYOB_FGXFRTfebxCsSYi0YwJo-oNu96bvZCuMplzRI1liZw'
            }
        ]
    }

    JWT_OIDC_TEST_PRIVATE_KEY_PEM = """-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDfn1nKQshOSj8xw44oC2klFWSNLmK3BnHONCJ1bZfq0EQ5gIfg
tlvB+Px8Ya+VS3OnK7Cdi4iU1fxO9ktN6c6TjmmmFevk8wIwqLthmCSF3r+3+h4e
ddj7hucMsXWv05QUrCPoL6YUUz7Cgpz7ra24rpAmK5z7lsV+f3BEvXkrUQIDAQAB
AoGAC0G3QGI6OQ6tvbCNYGCqq043YI/8MiBl7C5dqbGZmx1ewdJBhMNJPStuckhs
kURaDwk4+8VBW9SlvcfSJJrnZhgFMjOYSSsBtPGBIMIdM5eSKbenCCjO8Tg0BUh/
xa3CHST1W4RQ5rFXadZ9AeNtaGcWj2acmXNO3DVETXAX3x0CQQD13LrBTEDR44ei
lQ/4TlCMPO5bytd1pAxHnrqgMnWovSIPSShAAH1feFugH7ZGu7RoBO7pYNb6N3ia
C1idc7yjAkEA6Nfc6c8meTRkVRAHCF24LB5GLfsjoMB0tOeEO9w9Ous1a4o+D24b
AePMUImAp3woFoNDRfWtlNktOqLel5PjewJBAN9kBoA5o6/Rl9zeqdsIdWFmv4DB
5lEqlEnC7HlAP+3oo3jWFO9KQqArQL1V8w2D4aCd0uJULiC9pCP7aTHvBhcCQQDb
W0mOp436T6ZaELBfbFNulNLOzLLi5YzNRPLppfG1SRNZjbIrvTIKVL4N/YxLvQbT
NrQw+2OdQACBJiEHsdZzAkBcsTk7frTH4yGx0VfHxXDPjfTj4wmD6gZIlcIr9lZg
4H8UZcVFN95vEKxJiLRjAmj6g273pu9kK4ymXNEjWWJn
-----END RSA PRIVATE KEY-----"""

    CFS_BASE_URL = 'http://localhost:8080/paybc-api'
    CFS_CLIENT_ID = 'TEST'
    CFS_CLIENT_SECRET = 'TEST'
    PAYBC_PORTAL_URL = 'https://paydev.gov.bc.ca/public/directpay'

    SERVER_NAME = 'auth-web.dev.com'

    REPORT_API_BASE_URL = 'http://localhost:8080/reports-api/api/v1/reports'

    AUTH_API_ENDPOINT = 'http://localhost:8080/auth-api/'

    NATS_SUBJECT = 'entity.filing.test'

    BCOL_API_ENDPOINT = 'http://localhost:8080/bcol-api'

    VALID_REDIRECT_URLS = ['http://localhost:8080/*']

    TRANSACTION_REPORT_DEFAULT_TOTAL = 10

    PAYBC_DIRECT_PAY_API_KEY = 'TESTKEYSECRET'
    PAYBC_DIRECT_PAY_REF_NUMBER = 'REF1234'
    PAYBC_DIRECT_PAY_PORTAL_URL = 'https://paydev.gov.bc.ca/public/directsale'
    PAYBC_DIRECT_PAY_BASE_URL = 'http://localhost:8080/paybc-api'
    PAYBC_DIRECT_PAY_CLIENT_ID = 'TEST'
    PAYBC_DIRECT_PAY_CLIENT_SECRET = 'TEST'

    PAD_CONFIRMATION_PERIOD_IN_DAYS = 3
    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = 'mysecretkeyforbank'

    HOLIDAYS_LIST = os.getenv('HOLIDAYS_LIST', default='2021-Jan-01,2021-Feb-15,2021-Apr-02,2021-May-24,2021-Jul-1, '
                                                       '2021-Jul-1, 2021-Aug-2, 2021-Sep-6,2021-Oct-11, 2021-Nov-11, '
                                                       '2021-Dec-25')


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = _get_config('SECRET_KEY', default=None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False


class MigrationConfig():  # pylint: disable=too-few-public-methods
    """Config for db migration."""

    TESTING = False
    DEBUG = True

    # POSTGRESQL
    DB_USER = _get_config('DATABASE_USERNAME')
    DB_PASSWORD = _get_config('DATABASE_PASSWORD')
    DB_NAME = _get_config('DATABASE_NAME')
    DB_HOST = _get_config('DATABASE_HOST')
    DB_PORT = _get_config('DATABASE_PORT', default='5432')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
