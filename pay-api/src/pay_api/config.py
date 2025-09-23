# Copyright © 2024 Province of British Columbia
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

All items are loaded,
or have Constants defined here that are loaded into the Flask configuration.
All modules and lookups get their configuration from the Flask config,
rather than reading environment variables directly or by accessing this configuration directly.
"""

import base64
import os
import sys

from dotenv import find_dotenv, load_dotenv

# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    "development": "pay_api.config.DevConfig",
    "testing": "pay_api.config.TestConfig",
    "production": "pay_api.config.ProdConfig",
    "default": "pay_api.config.ProdConfig",
    "migration": "pay_api.config.MigrationConfig",
}


def get_named_config(config_name: str = "production"):
    """Return the configuration object based on the name.

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ["production", "staging", "default"]:
        config = ProdConfig()
    elif config_name == "testing":
        config = TestConfig()
    elif config_name == "development":
        config = DevConfig()
    elif config_name == "migration":
        config = MigrationConfig()
    else:
        raise KeyError(f'Unknown configuration "{config_name}"')
    return config


def _get_config(config_key: str, **kwargs):
    """Get the config from environment, and throw error if there are no default values and if the value is None."""
    if "default" in kwargs:
        value = os.getenv(config_key, kwargs.get("default"))
    else:
        value = os.getenv(config_key)
    return value


class _Config:  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults for all the other configurations."""

    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
    CLOUD_PLATFORM = os.getenv("CLOUD_PLATFORM", "OCP")
    LOGGING_OVERRIDE_CONFIG = None
    if logging_config_value := os.getenv("LOGGING_OVERRIDE_CONFIG"):
        try:
            LOGGING_OVERRIDE_CONFIG = base64.b64decode(logging_config_value).decode("utf-8")
        except Exception:
            LOGGING_OVERRIDE_CONFIG = None

    SECRET_KEY = "a secret"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,  # Base connection pool size - Default 5
        "max_overflow": 3,  # Additional connections when needed - Default 10
        "pool_pre_ping": True,  # Test connections before use - Default False
        "pool_recycle": 300,  # Recycle connections 5m - Default 1800
        "pool_timeout": 30,  # Timeout for getting connection - Default 30
        "pool_use_lifo": True,
    }

    ALEMBIC_INI = "migrations/alembic.ini"

    PAY_LD_SDK_KEY = _get_config("PAY_LD_SDK_KEY")

    # POSTGRESQL
    DB_USER = _get_config("DATABASE_USERNAME")
    DB_PASSWORD = _get_config("DATABASE_PASSWORD")
    DB_NAME = _get_config("DATABASE_NAME")
    DB_HOST = _get_config("DATABASE_HOST")
    DB_PORT = _get_config("DATABASE_PORT", default="5432")
    SQLALCHEMY_ECHO = _get_config("SQLALCHEMY_ECHO", default="False").lower() == "true"

    # POSTGRESQL
    if DB_UNIX_SOCKET := os.getenv("DATABASE_UNIX_SOCKET", None):
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?unix_sock={DB_UNIX_SOCKET}/.s.PGSQL.5432"
        )
    else:
        SQLALCHEMY_DATABASE_URI = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # JWT_OIDC Settings
    JWT_OIDC_WELL_KNOWN_CONFIG = _get_config("JWT_OIDC_WELL_KNOWN_CONFIG")
    JWT_OIDC_ALGORITHMS = _get_config("JWT_OIDC_ALGORITHMS")
    JWT_OIDC_ISSUER = _get_config("JWT_OIDC_ISSUER")
    JWT_OIDC_AUDIENCE = _get_config("JWT_OIDC_AUDIENCE")
    JWT_OIDC_CLIENT_SECRET = _get_config("JWT_OIDC_CLIENT_SECRET")
    JWT_OIDC_CACHING_ENABLED = _get_config("JWT_OIDC_CACHING_ENABLED", default=False)
    JWT_OIDC_JWKS_CACHE_TIMEOUT = int(_get_config("JWT_OIDC_JWKS_CACHE_TIMEOUT", default=300))

    # CFS API Settings
    CFS_BASE_URL = _get_config("CFS_BASE_URL")
    CFS_CLIENT_ID = _get_config("CFS_CLIENT_ID")
    CFS_CLIENT_SECRET = _get_config("CFS_CLIENT_SECRET")
    PAYBC_PORTAL_URL = _get_config("PAYBC_PORTAL_URL")
    CONNECT_TIMEOUT = int(_get_config("CONNECT_TIMEOUT", default=10))
    GENERATE_RANDOM_INVOICE_NUMBER = _get_config("CFS_GENERATE_RANDOM_INVOICE_NUMBER", default="False")
    CFS_ACCOUNT_DESCRIPTION = _get_config("CFS_ACCOUNT_DESCRIPTION", default="BCR")
    CFS_INVOICE_PREFIX = os.getenv("CFS_INVOICE_PREFIX", "REG")
    CFS_RECEIPT_PREFIX = os.getenv("CFS_RECEIPT_PREFIX", "RCPT")
    CFS_PARTY_PREFIX = os.getenv("CFS_PARTY_PREFIX", "BCR-")
    PAY_CONNECTOR_AUTH = os.getenv("PAY_CONNECTOR_AUTH", "")

    # EFT Config
    EFT_INVOICE_PREFIX = os.getenv("EFT_INVOICE_PREFIX", "REG")

    # PAYBC Direct Pay Settings
    PAYBC_DIRECT_PAY_REF_NUMBER = _get_config("PAYBC_DIRECT_PAY_REF_NUMBER")
    PAYBC_DIRECT_PAY_API_KEY = _get_config("PAYBC_DIRECT_PAY_API_KEY")
    PAYBC_DIRECT_PAY_PORTAL_URL = _get_config("PAYBC_DIRECT_PAY_PORTAL_URL")
    PAYBC_DIRECT_PAY_BASE_URL = _get_config("PAYBC_DIRECT_PAY_BASE_URL")
    PAYBC_DIRECT_PAY_CLIENT_ID = _get_config("PAYBC_DIRECT_PAY_CLIENT_ID")
    PAYBC_DIRECT_PAY_CLIENT_SECRET = _get_config("PAYBC_DIRECT_PAY_CLIENT_SECRET")
    PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL = _get_config("PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL")

    # PUB/SUB - PUB: auth-event-dev, account-mailer-dev, business-pay-dev, namex-pay-dev
    ACCOUNT_MAILER_TOPIC = os.getenv("ACCOUNT_MAILER_TOPIC", "account-mailer-dev")
    AUTH_EVENT_TOPIC = os.getenv("AUTH_EVENT_TOPIC", "auth-event-dev")
    BUSINESS_PAY_TOPIC = os.getenv("BUSINESS_PAY_TOPIC", "business-pay-dev")
    GCP_AUTH_KEY = os.getenv("AUTHPAY_GCP_AUTH_KEY", None)
    NAMEX_PAY_TOPIC = os.getenv("NAMEX_PAY_TOPIC", "namex-pay-dev")
    STRR_PAY_TOPIC = os.getenv("STRR_PAY_TOPIC", BUSINESS_PAY_TOPIC)
    ASSETS_PAY_TOPIC = os.getenv("ASSETS_PAY_TOPIC", "assets-pay-notification-dev")

    # API Endpoints
    AUTH_API_URL = os.getenv("AUTH_API_URL", "")
    AUTH_API_VERSION = os.getenv("AUTH_API_VERSION", "")
    BCOL_API_URL = os.getenv("BCOL_API_URL", "")
    BCOL_API_VERSION = os.getenv("BCOL_API_VERSION", "")
    REPORT_API_URL = os.getenv("REPORT_API_URL", "")
    REPORT_API_VERSION = os.getenv("REPORT_API_VERSION", "")

    AUTH_API_ENDPOINT = f"{AUTH_API_URL + AUTH_API_VERSION}/"
    REPORT_API_BASE_URL = f"{REPORT_API_URL + REPORT_API_VERSION}/reports"
    BCOL_API_ENDPOINT = f"{BCOL_API_URL + BCOL_API_VERSION}/"

    AUTH_WEB_URL = os.getenv("AUTH_WEB_URL", "")
    PAY_WEB_URL = os.getenv("PAY_WEB_URL", "")
    NOTIFY_API_URL = os.getenv("NOTIFY_API_URL", "")
    NOTIFY_API_VERSION = os.getenv("NOTIFY_API_VERSION", "")
    NOTIFY_API_ENDPOINT = f"{NOTIFY_API_URL + NOTIFY_API_VERSION}/"
    IT_OPS_EMAIL = os.getenv("IT_OPS_EMAIL", "").split(",")

    # Disable valid redirect URLs - for DEV only
    DISABLE_VALID_REDIRECT_URLS = _get_config("DISABLE_VALID_REDIRECT_URLS", default="False").lower() == "true"

    # Valid Payment redirect URLs
    VALID_REDIRECT_URLS = [
        (val.strip() if val != "" else None) for val in _get_config("VALID_REDIRECT_URLS", default="").split(",")
    ]

    # Service account details
    KEYCLOAK_SERVICE_ACCOUNT_ID = _get_config("SBC_PAY_CLIENT_ID")
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = _get_config("SBC_PAY_CLIENT_SECRET")

    # Default number of transactions to be returned for transaction reporting
    TRANSACTION_REPORT_DEFAULT_TOTAL = int(_get_config("TRANSACTION_REPORT_DEFAULT_TOTAL", default=50))

    # Default number of routing slips to be returned for routing slip search
    ROUTING_SLIP_DEFAULT_TOTAL = int(_get_config("ROUTING_SLIP_DEFAULT_TOTAL", default=50))

    PAD_CONFIRMATION_PERIOD_IN_DAYS = int(_get_config("PAD_CONFIRMATION_PERIOD_IN_DAYS", default=3))

    # legislative timezone for future effective dating
    LEGISLATIVE_TIMEZONE = os.getenv("LEGISLATIVE_TIMEZONE", "America/Vancouver")

    # BCOL user name for Service account payments
    BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS = os.getenv(
        "BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS", "BCROS SERVICE ACCOUNT"
    )

    # The number of characters which can be exposed to admins for a bank account number
    MASK_LEN = int(_get_config("MASK_LEN", default=3))

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv("ACCOUNT_SECRET_KEY")

    OUTSTANDING_TRANSACTION_DAYS = int(os.getenv("OUTSTANDING_TRANSACTION_DAYS", "10"))

    ALLOW_LEGACY_ROUTING_SLIPS = os.getenv("ALLOW_LEGACY_ROUTING_SLIPS", "True").lower() == "true"

    # Used for DEV/TEST/SANDBOX only. If True, will skip payment and return success and send queue message.
    ALLOW_SKIP_PAYMENT = os.getenv("ALLOW_SKIP_PAYMENT", "False").lower() == "true"
    ENABLE_403_LOGGING = os.getenv("ENABLE_403_LOGGING", "False").lower() == "true"

    # To differentiate between local, dev, test, sandbox, prod
    ENVIRONMENT_NAME = os.getenv("ENVIRONMENT_NAME", "local")

    EXECUTOR_PROPAGATE_EXCEPTIONS = True

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

    USE_TEST_KEYCLOAK_DOCKER = _get_config("USE_TEST_KEYCLOAK_DOCKER", default=None)
    USE_DOCKER_MOCK = _get_config("USE_DOCKER_MOCK", default=None)

    # POSTGRESQL
    DB_USER = _get_config("DATABASE_TEST_USERNAME", default="postgres")
    DB_PASSWORD = _get_config("DATABASE_TEST_PASSWORD", default="postgres")
    DB_NAME = _get_config("DATABASE_TEST_NAME", default="paytestdb")
    DB_HOST = _get_config("DATABASE_TEST_HOST", default="localhost")
    DB_PORT = _get_config("DATABASE_TEST_PORT", default="5432")

    # Use different databases for parallel test isolation
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    if worker_id == "master":
        DB_NAME = "pay-test"
    else:
        DB_NAME = f"pay-test-{worker_id}"

    SQLALCHEMY_DATABASE_URI = _get_config(
        "DATABASE_TEST_URL", default=f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"
    )
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.rsplit("/", 1)[0] + f"/{DB_NAME}"

    JWT_OIDC_TEST_MODE = True
    # JWT_OIDC_ISSUER = _get_config('JWT_OIDC_TEST_ISSUER')
    JWT_OIDC_TEST_AUDIENCE = _get_config("JWT_OIDC_TEST_AUDIENCE")
    JWT_OIDC_TEST_CLIENT_SECRET = _get_config("JWT_OIDC_TEST_CLIENT_SECRET")
    JWT_OIDC_TEST_ISSUER = _get_config("JWT_OIDC_TEST_ISSUER")
    JWT_OIDC_WELL_KNOWN_CONFIG = _get_config("JWT_OIDC_WELL_KNOWN_CONFIG")
    JWT_OIDC_TEST_ALGORITHMS = _get_config("JWT_OIDC_TEST_ALGORITHMS")
    JWT_OIDC_TEST_JWKS_URI = _get_config("JWT_OIDC_TEST_JWKS_URI", default=None)

    JWT_OIDC_TEST_KEYS = {
        "keys": [
            {
                "kid": "sbc-auth-web",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-"
                "TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR",
                "e": "AQAB",
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
                "n": "AN-fWcpCyE5KPzHDjigLaSUVZI0uYrcGcc40InVtl-rQRDmAh-C2W8H4_Hxhr5VLc6crsJ2LiJTV_E72S03pzpOOaaYV6-"
                "TzAjCou2GYJIXev7f6Hh512PuG5wyxda_TlBSsI-gvphRTPsKCnPutrbiukCYrnPuWxX5_cES9eStR",
                "e": "AQAB",
                "d": "C0G3QGI6OQ6tvbCNYGCqq043YI_8MiBl7C5dqbGZmx1ewdJBhMNJPStuckhskURaDwk4-"
                "8VBW9SlvcfSJJrnZhgFMjOYSSsBtPGBIMIdM5eSKbenCCjO8Tg0BUh_"
                "xa3CHST1W4RQ5rFXadZ9AeNtaGcWj2acmXNO3DVETXAX3x0",
                "p": "APXcusFMQNHjh6KVD_hOUIw87lvK13WkDEeeuqAydai9Ig9JKEAAfV94W6Aftka7tGgE7ulg1vo3eJoLWJ1zvKM",
                "q": "AOjX3OnPJnk0ZFUQBwhduCweRi37I6DAdLTnhDvcPTrrNWuKPg9uGwHjzFCJgKd8KBaDQ0X1rZTZLTqi3peT43s",
                "dp": "AN9kBoA5o6_Rl9zeqdsIdWFmv4DB5lEqlEnC7HlAP-3oo3jWFO9KQqArQL1V8w2D4aCd0uJULiC9pCP7aTHvBhc",
                "dq": "ANtbSY6njfpPploQsF9sU26U0s7MsuLljM1E8uml8bVJE1mNsiu9MgpUvg39jEu9BtM2tDD7Y51AAIEmIQex1nM",
                "qi": "XLE5O360x-MhsdFXx8Vwz4304-MJg-oGSJXCK_ZWYOB_FGXFRTfebxCsSYi0YwJo-oNu96bvZCuMplzRI1liZw",
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

    CFS_BASE_URL = "http://localhost:8080/paybc-api"
    CFS_CLIENT_ID = "TEST"
    CFS_CLIENT_SECRET = "TEST"
    PAYBC_PORTAL_URL = "https://paydev.gov.bc.ca/public/directpay"

    SERVER_NAME = "auth-web.dev.com"

    REPORT_API_BASE_URL = "http://localhost:8080/reports-api/api/v1/reports"

    AUTH_API_ENDPOINT = "http://localhost:8080/auth-api/"

    BCOL_API_ENDPOINT = "http://localhost:8080/bcol-api/"

    VALID_REDIRECT_URLS = ["http://localhost:8080/*"]

    TRANSACTION_REPORT_DEFAULT_TOTAL = 10

    PAYBC_DIRECT_PAY_API_KEY = "TESTKEYSECRET"
    PAYBC_DIRECT_PAY_REF_NUMBER = "REF1234"
    PAYBC_DIRECT_PAY_PORTAL_URL = "https://paydev.gov.bc.ca/public/directsale"
    PAYBC_DIRECT_PAY_BASE_URL = "http://localhost:8080/paybc-api"
    PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL = PAYBC_DIRECT_PAY_BASE_URL
    PAYBC_DIRECT_PAY_CLIENT_ID = "TEST"
    PAYBC_DIRECT_PAY_CLIENT_SECRET = "TEST"

    PAD_CONFIRMATION_PERIOD_IN_DAYS = 3
    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = "mysecretkeyforbank"
    ALLOW_SKIP_PAYMENT = False

    # Google Cloud Storage emulator settings for testing
    GCS_EMULATOR_HOST = "http://localhost:4443"


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = _get_config("SECRET_KEY", default=None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print("WARNING: SECRET_KEY being set as a one-shot", file=sys.stderr)

    TESTING = False
    DEBUG = False


class MigrationConfig:  # pylint: disable=too-few-public-methods
    """Config for db migration."""

    TESTING = False
    DEBUG = True

    # POSTGRESQL
    DB_USER = _get_config("DATABASE_USERNAME")
    DB_PASSWORD = _get_config("DATABASE_PASSWORD")
    DB_NAME = _get_config("DATABASE_NAME")
    DB_HOST = _get_config("DATABASE_HOST")
    DB_PORT = _get_config("DATABASE_PORT", default="5432")
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
