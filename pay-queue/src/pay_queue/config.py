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
    "development": "pay_queue.config.DevConfig",
    "testing": "pay_queue.config.TestConfig",
    "production": "pay_queue.config.ProdConfig",
    "default": "pay_queue.config.ProdConfig",
}


def get_named_config(config_name: str = "production"):
    """Return the configuration object based on the name.

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ["production", "staging", "default"]:
        app_config = ProdConfig()
    elif config_name == "testing":
        app_config = TestConfig()
    elif config_name == "development":
        app_config = DevConfig()
    else:
        raise KeyError(f"Unknown configuration: {config_name}")
    return app_config


def get_comma_delimited_string_as_tuple(value: str) -> tuple:
    """Get comma delimited string as a tuple."""
    return tuple(val.strip() for val in value.split(",") if val.strip())


class _Config:  # pylint: disable=too-few-public-methods,protected-access
    """Base class configuration that should set reasonable defaults.

    Used as the base for all the other configurations.
    """

    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
    PAY_LD_SDK_KEY = os.getenv("PAY_LD_SDK_KEY", None)
    LEGISLATIVE_TIMEZONE = os.getenv("LEGISLATIVE_TIMEZONE", "America/Vancouver")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # POSTGRESQL
    DB_USER = os.getenv("DATABASE_USERNAME", "")
    DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DB_NAME = os.getenv("DATABASE_NAME", "")
    DB_HOST = os.getenv("DATABASE_HOST", "")
    DB_PORT = os.getenv("DATABASE_PORT", "5432")
    if DB_UNIX_SOCKET := os.getenv("DATABASE_UNIX_SOCKET", None):
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?host={DB_UNIX_SOCKET}&port={DB_PORT}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"

    # CFS API Settings
    CFS_BASE_URL = os.getenv("CFS_BASE_URL")
    CFS_CLIENT_ID = os.getenv("CFS_CLIENT_ID")
    CFS_CLIENT_SECRET = os.getenv("CFS_CLIENT_SECRET")
    CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "10"))
    PAY_CONNECTOR_AUTH = os.getenv("PAY_CONNECTOR_AUTH", "")

    # EFT Config
    EFT_TDI17_LOCATION_ID = os.getenv("EFT_TDI17_LOCATION_ID")
    EFT_WIRE_PATTERNS = get_comma_delimited_string_as_tuple(os.getenv("EFT_WIRE_PATTERNS", ""))
    EFT_PATTERNS = get_comma_delimited_string_as_tuple(os.getenv("EFT_PATTERNS", ""))

    # PAD Config
    PAD_NSF_NOTIFY_EMAILS = os.getenv("PAD_NSF_NOTIFY_EMAILS", "")

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv("ACCOUNT_SECRET_KEY")

    KEYCLOAK_SERVICE_ACCOUNT_ID = os.getenv("SBC_PAY_CLIENT_ID")
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = os.getenv("SBC_PAY_CLIENT_SECRET")
    JWT_OIDC_ISSUER = os.getenv("JWT_OIDC_ISSUER")
    NOTIFY_API_URL = os.getenv("NOTIFY_API_URL", "")
    NOTIFY_API_VERSION = os.getenv("NOTIFY_API_VERSION", "")
    NOTIFY_API_ENDPOINT = f"{NOTIFY_API_URL + NOTIFY_API_VERSION}/"
    IT_OPS_EMAIL = os.getenv("IT_OPS_EMAIL", "").split(",")

    DISABLE_EJV_ERROR_EMAIL = os.getenv("DISABLE_EJV_ERROR_EMAIL", "true").lower() == "true"
    DISABLE_CSV_ERROR_EMAIL = os.getenv("DISABLE_CSV_ERROR_EMAIL", "true").lower() == "true"
    DISABLE_AP_ERROR_EMAIL = os.getenv("DISABLE_AP_ERROR_EMAIL", "true").lower() == "true"

    # PUB/SUB - PUB: account-mailer-dev, auth-event-dev, SUB to ftp-poller-payment-reconciliation-dev, business-events
    ACCOUNT_MAILER_TOPIC = os.getenv("ACCOUNT_MAILER_TOPIC", "account-mailer-dev")
    AUTH_EVENT_TOPIC = os.getenv("AUTH_EVENT_TOPIC", "auth-event-dev")
    BUSINESS_PAY_TOPIC = os.getenv("BUSINESS_PAY_TOPIC", "business-pay-topic")
    NAMEX_PAY_TOPIC = os.getenv("NAMEX_PAY_TOPIC", "namex-pay-dev")
    STRR_PAY_TOPIC = os.getenv("STRR_PAY_TOPIC", BUSINESS_PAY_TOPIC)
    ASSETS_PAY_TOPIC = os.getenv("ASSETS_PAY_TOPIC", "assets-pay-notification-dev")

    # If blank in PUBSUB, this should match the https endpoint the subscription is pushing to.
    PAY_AUDIENCE_SUB = os.getenv("PAY_AUDIENCE_SUB", None)
    VERIFY_PUBSUB_EMAILS = f"{os.getenv('AUTHPAY_SERVICE_ACCOUNT')},{os.getenv('BUSINESS_SERVICE_ACCOUNT')}".split(",")
    SKIP_EXCEPTION_FOR_TEST_ENVIRONMENT = os.getenv("SKIP_EXCEPTION_FOR_TEST_ENVIRONMENT", "").lower() == "true"

    # Google Cloud Storage settings
    GOOGLE_STORAGE_SA = os.getenv("GOOGLE_STORAGE_SA", "")
    GOOGLE_BUCKET_NAME = os.getenv("FTP_POLLER_BUCKET_NAME")
    GOOGLE_BUCKET_FOLDER_CGI_PROCESSING = os.getenv("GOOGLE_BUCKET_FOLDER_CGI_PROCESSING", "cgi_processing")
    GOOGLE_BUCKET_FOLDER_CGI_PROCESSED = os.getenv("GOOGLE_BUCKET_FOLDER_CGI_PROCESSED", "cgi_processed")
    GOOGLE_BUCKET_FOLDER_CGI_FEEDBACK = os.getenv("GOOGLE_BUCKET_FOLDER_CGI_FEEDBACK", "cgi_feedback")
    GOOGLE_BUCKET_FOLDER_AR = os.getenv("GOOGLE_BUCKET_FOLDER_AR", "ar")
    GOOGLE_BUCKET_FOLDER_EFT = os.getenv("GOOGLE_BUCKET_FOLDER_EFT", "eft")


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
    DB_USER = os.getenv("DATABASE_TEST_USERNAME", "")
    DB_PASSWORD = os.getenv("DATABASE_TEST_PASSWORD", "")
    DB_NAME = os.getenv("DATABASE_TEST_NAME", "")
    DB_HOST = os.getenv("DATABASE_TEST_HOST", "")
    DB_PORT = os.getenv("DATABASE_TEST_PORT", "5432")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_TEST_URL",
        default=f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}",
    )

    USE_DOCKER_MOCK = os.getenv("USE_DOCKER_MOCK", None)

    CFS_BASE_URL = "http://localhost:8080/paybc-api"
    CFS_CLIENT_ID = "TEST"  # Test value only
    CFS_CLIENT_SECRET = "TEST"  # noqa: S105  # Test value only

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv("ACCOUNT_SECRET_KEY", "test")

    # Secrets for integration tests
    TEST_GCP_PROJECT_NAME = "pay-queue-dev"
    # Needs to have ftp-poller-dev in it.
    TEST_GCP_TOPICS = [
        "account-mailer-dev",
        "ftp-poller-dev",
        "business-identifier-update-pay-dev",
    ]
    TEST_PUSH_ENDPOINT_PORT = 5020
    TEST_PUSH_ENDPOINT = os.getenv(
        "TEST_PUSH_ENDPOINT",
        f"http://host.docker.internal:{TEST_PUSH_ENDPOINT_PORT!s}/",
    )
    DISABLE_EJV_ERROR_EMAIL = False
    DISABLE_CSV_ERROR_EMAIL = False
    # Need a value for this, so we can mock the publish client.
    BUSINESS_PAY_TOPIC = "business-pay-topic"

    # Google Cloud Storage emulator settings for testing
    GCS_EMULATOR_HOST = "http://localhost:4443"


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    TESTING = False
    DEBUG = False
