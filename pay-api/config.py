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

import json
import os
import sys

from dotenv import find_dotenv, load_dotenv

# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    'development': 'config.DevConfig',
    'testing': 'config.TestConfig',
    'production': 'config.ProdConfig',
    'default': 'config.ProdConfig',
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


def _get_config(config_key: str, **kwargs):
    """Get the config from environment, and throw error if there are no default values and if the value is None."""
    if 'default' in kwargs:
        value = os.getenv(config_key, kwargs.get('default'))
    else:
        value = os.getenv(config_key)
        # assert value TODO Un-comment once we find a solution to run pre-hook without initializing app
    return value


class _Config(object):  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults for all the other configurations. """

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
    SQLALCHEMY_DATABASE_URI = 'postgresql://{user}:{password}@{host}:{port}/{name}'.format(
        user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=int(DB_PORT), name=DB_NAME
    )
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

    # PAYBC API Settings
    PAYBC_BASE_URL = _get_config('PAYBC_BASE_URL')
    PAYBC_CLIENT_ID = _get_config('PAYBC_CLIENT_ID')
    PAYBC_CLIENT_SECRET = _get_config('PAYBC_CLIENT_SECRET')
    PAYBC_PORTAL_URL = _get_config('PAYBC_PORTAL_URL')
    CONNECT_TIMEOUT = int(_get_config('PAYBC_CONNECT_TIMEOUT', default=10))
    GENERATE_RANDOM_INVOICE_NUMBER = _get_config('PAYBC_GENERATE_RANDOM_INVOICE_NUMBER', default='False')

    # REPORT API Settings
    REPORT_API_BASE_URL = _get_config('REPORT_API_BASE_URL')

    # NATS Config
    NATS_SERVERS = _get_config('NATS_SERVERS', default='nats://127.0.0.1:4222').split(',')
    NATS_CLIENT_NAME = _get_config('NATS_CLIENT_NAME', default='entity.filing.worker')
    NATS_CLUSTER_ID = _get_config('NATS_CLUSTER_ID', default='test-cluster')
    NATS_SUBJECT = _get_config('NATS_SUBJECT', default='entity.filings')
    NATS_QUEUE = _get_config('NATS_QUEUE', default='filing-worker')

    # Auth API Endpoint
    AUTH_API_ENDPOINT = _get_config('AUTH_API_ENDPOINT')

    # Sentry Config
    SENTRY_DSN = _get_config('SENTRY_DSN', default=None)

    # BCOL Service
    BCOL_API_ENDPOINT = _get_config('BCOL_API_ENDPOINT')

    # Valid Payment redirect URLs
    VALID_REDIRECT_URLS = [(val.strip() if val != '' else None)
                           for val in _get_config('VALID_REDIRECT_URLS', default='').split(',')]

    # Service account details
    KEYCLOAK_SERVICE_ACCOUNT_ID = _get_config('KEYCLOAK_SERVICE_ACCOUNT_ID')
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = _get_config('KEYCLOAK_SERVICE_ACCOUNT_SECRET')

    # Default number of transactions to be returned for transaction reporting
    TRANSACTION_REPORT_DEFAULT_TOTAL = int(_get_config('TRANSACTION_REPORT_DEFAULT_TOTAL', default=50))

    # legislative timezone for future effective dating
    LEGISLATIVE_TIMEZONE = os.getenv('LEGISLATIVE_TIMEZONE', 'America/Vancouver')

    # Till direct pay is fully ready , keep this value false
    DIRECT_PAY_ENABLED = os.getenv('DIRECT_PAY_ENABLED', 'False').lower() == 'true'

    # BCOL user name for Service account payments
    BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS = os.getenv('BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS',
                                                           'BCROS SERVICE ACCOUNT')

    TESTING = False
    DEBUG = True


class DevConfig(_Config):  # pylint: disable=too-few-public-methods
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
        default='postgresql://{user}:{password}@{host}:{port}/{name}'.format(
            user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=int(DB_PORT), name=DB_NAME
        ),
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
        "keys": [
            {
                "kid": "sbc-auth-web",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR",
                "e": "AQAB"
            }
        ]
    }

    JWT_OIDC_TEST_PRIVATE_KEY_JWKS = {
        "keys": [
            {
                "kid": "sbc-auth-web",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR",
                "e": "AQAB",
                "d": "C0G3QGI6OQ6tvbCNYGCqq043YI_8MiBl7C5dqbGZmx1ewdJBhMNJPStuckhskURaDwk4-8VBW9SlvcfSJJrnZhgFMjOYSSsBtPGBIMIdM5eSKbenCCjO8Tg0BUh_xa3CHST1W4RQ5rFXadZ9AeNtaGcWj2acmXNO3DVETXAX3x0",
                "p": "APXcusFMQNHjh6KVD_hOUIw87lvK13WkDEeeuqAydai9Ig9JKEAAfV94W6Aftka7tGgE7ulg1vo3eJoLWJ1zvKM",
                "q": "AOjX3OnPJnk0ZFUQBwhduCweRi37I6DAdLTnhDvcPTrrNWuKPg9uGwHjzFCJgKd8KBaDQ0X1rZTZLTqi3peT43s",
                "dp": "AN9kBoA5o6_Rl9zeqdsIdWFmv4DB5lEqlEnC7HlAP-3oo3jWFO9KQqArQL1V8w2D4aCd0uJULiC9pCP7aTHvBhc",
                "dq": "ANtbSY6njfpPploQsF9sU26U0s7MsuLljM1E8uml8bVJE1mNsiu9MgpUvg39jEu9BtM2tDD7Y51AAIEmIQex1nM",
                "qi": "XLE5O360x-MhsdFXx8Vwz4304-MJg-oGSJXCK_ZWYOB_FGXFRTfebxCsSYi0YwJo-oNu96bvZCuMplzRI1liZw"
            }
        ]
    }

    JWT_OIDC_TEST_PRIVATE_KEY_PEM = """
    -----BEGIN RSA PRIVATE KEY-----
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

    PAYBC_BASE_URL = 'http://localhost:8080/paybc-api'
    PAYBC_CLIENT_ID = 'TEST'
    PAYBC_CLIENT_SECRET = 'TEST'
    PAYBC_PORTAL_URL = ''
    SERVER_NAME = 'auth-web.dev.com'

    REPORT_API_BASE_URL = "http://localhost:8080/reports-api/api/v1/reports"

    AUTH_API_ENDPOINT = "http://localhost:8080/auth-api/"

    NATS_SUBJECT = 'entity.filing.test'

    BCOL_API_ENDPOINT = 'http://localhost:8080/bcol-api'

    VALID_REDIRECT_URLS = ['http://localhost:8080/*']

    TRANSACTION_REPORT_DEFAULT_TOTAL = 10


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = _get_config('SECRET_KEY', default=None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False
