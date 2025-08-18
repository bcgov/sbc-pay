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
    "development": "config.DevConfig",
    "testing": "config.TestConfig",
    "production": "config.ProdConfig",
    "default": "config.ProdConfig",
}


def get_named_config(config_name: str = "production"):
    """Return the configuration object based on the name

    :raise: KeyError: if an unknown configuration is requested
    """
    if config_name in ["production", "staging", "default"]:
        config = ProdConfig()
    elif config_name == "testing":
        config = TestConfig()
    elif config_name == "development":
        config = DevConfig()
    else:
        raise KeyError(f"Unknown configuration '{config_name}'")
    return config


class _Config(object):  # pylint: disable=too-few-public-methods
    """Base class configuration that should set reasonable defaults for all the other configurations."""

    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

    SECRET_KEY = "a secret"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALEMBIC_INI = "migrations/alembic.ini"

    PAY_LD_SDK_KEY = os.getenv("PAY_LD_SDK_KEY", None)

    # POSTGRESQL
    DB_USER = os.getenv("DATABASE_USERNAME", "")
    DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DB_NAME = os.getenv("DATABASE_NAME", "")
    DB_HOST = os.getenv("DATABASE_HOST", "")
    DB_PORT = os.getenv("DATABASE_PORT", "5432")
    if DB_UNIX_SOCKET := os.getenv("DATABASE_UNIX_SOCKET", None):
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?unix_sock={DB_UNIX_SOCKET}/.s.PGSQL.5432"
        )
    else:
        SQLALCHEMY_DATABASE_URI = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"
    SQLALCHEMY_ECHO = False

    # Data Warehouse Settings
    DW_UNIX_SOCKET = os.getenv("DW_UNIX_SOCKET", "")
    DW_NAME = os.getenv("DW_NAME", "")
    DW_IAM_USER = os.getenv("DW_IAM_USER", "")

    # PAYBC Direct Pay Settings
    PAYBC_DIRECT_PAY_REF_NUMBER = os.getenv("PAYBC_DIRECT_PAY_REF_NUMBER")
    PAYBC_DIRECT_PAY_API_KEY = os.getenv("PAYBC_DIRECT_PAY_API_KEY")
    PAYBC_DIRECT_PAY_BASE_URL = os.getenv("PAYBC_DIRECT_PAY_BASE_URL")
    PAYBC_DIRECT_PAY_CLIENT_ID = os.getenv("PAYBC_DIRECT_PAY_CLIENT_ID")
    PAYBC_DIRECT_PAY_CLIENT_SECRET = os.getenv("PAYBC_DIRECT_PAY_CLIENT_SECRET")

    # CFS API Settings
    CFS_BASE_URL = os.getenv("CFS_BASE_URL")
    CFS_CLIENT_ID = os.getenv("CFS_CLIENT_ID")
    CFS_CLIENT_SECRET = os.getenv("CFS_CLIENT_SECRET")
    CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", 10))
    GENERATE_RANDOM_INVOICE_NUMBER = os.getenv("CFS_GENERATE_RANDOM_INVOICE_NUMBER", "False")
    PAY_CONNECTOR_AUTH = os.getenv("PAY_CONNECTOR_AUTH", "")

    # legislative timezone for future effective dating
    LEGISLATIVE_TIMEZONE = os.getenv("LEGISLATIVE_TIMEZONE", "America/Vancouver")

    # API Endpoints
    AUTH_API_URL = os.getenv("AUTH_API_URL", "")
    AUTH_API_VERSION = os.getenv("AUTH_API_VERSION", "")
    NOTIFY_API_URL = os.getenv("NOTIFY_API_URL", "")
    NOTIFY_API_VERSION = os.getenv("NOTIFY_API_VERSION", "")

    AUTH_API_ENDPOINT = f"{AUTH_API_URL + AUTH_API_VERSION}/"
    NOTIFY_API_ENDPOINT = f"{NOTIFY_API_URL + NOTIFY_API_VERSION}/"

    # Service account details
    KEYCLOAK_SERVICE_ACCOUNT_ID = os.getenv("SBC_PAY_CLIENT_ID")
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = os.getenv("SBC_PAY_CLIENT_SECRET")

    # JWT_OIDC Settings
    JWT_OIDC_ISSUER = os.getenv("JWT_OIDC_ISSUER")

    # Front end url
    AUTH_WEB_URL = os.getenv("AUTH_WEB_PAY_TRANSACTION_URL", "")
    AUTH_WEB_STATEMENT_URL = os.getenv("AUTH_WEB_STATEMENT_URL", "account/orgId/settings/statements")
    REGISTRIES_LOGO_IMAGE_NAME = os.getenv("REGISTRIES_LOGO_IMAGE_NAME", "bc_logo_for_email.png")
    PAY_WEB_URL = os.getenv("PAY_WEB_PAY_URL", "")

    # GCP PubSub
    GCP_AUTH_KEY = os.getenv("AUTHPAY_GCP_AUTH_KEY", None)
    ACCOUNT_MAILER_TOPIC = os.getenv("ACCOUNT_MAILER_TOPIC", None)
    AUTH_EVENT_TOPIC = os.getenv("AUTH_EVENT_TOPIC", None)
    BUSINESS_PAY_TOPIC = os.getenv("BUSINESS_PAY_TOPIC", "business-pay-topic")
    NAMEX_PAY_TOPIC = os.getenv("NAMEX_PAY_TOPIC", "namex-pay-dev")
    STRR_PAY_TOPIC = os.getenv("STRR_PAY_TOPIC", BUSINESS_PAY_TOPIC)
    ASSETS_PAY_TOPIC = os.getenv("ASSETS_PAY_TOPIC", "assets-pay-notification-dev")

    CFS_ACCOUNT_DESCRIPTION = os.getenv("CFS_ACCOUNT_DESCRIPTION", "BCR")
    CFS_INVOICE_PREFIX = os.getenv("CFS_INVOICE_PREFIX", "REG")
    CFS_STOP_PAD_ACCOUNT_CREATION = os.getenv("CFS_STOP_PAD_ACCOUNT_CREATION", "false").lower() == "true"
    CFS_PARTY_PREFIX = os.getenv("CFS_PARTY_PREFIX", "BCR-")

    # The number of characters which can be exposed to admins for a bank account number
    MASK_LEN = int(os.getenv("MASK_LEN", 3))

    TESTING = False
    DEBUG = True
    PAD_CONFIRMATION_PERIOD_IN_DAYS = int(os.getenv("PAD_CONFIRMATION_PERIOD_IN_DAYS", "3"))

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv("ACCOUNT_SECRET_KEY")

    # EJV config variables
    CGI_FEEDER_NUMBER = os.getenv("CGI_FEEDER_NUMBER")
    CGI_MINISTRY_PREFIX = os.getenv("CGI_MINISTRY_PREFIX")
    CGI_DISBURSEMENT_DESC = os.getenv("CGI_DISBURSEMENT_DESC", "BCREGISTRIES {} {} DISBURSEMENTS")
    CGI_MESSAGE_VERSION = os.getenv("CGI_MESSAGE_VERSION", "4010")
    CGI_BCREG_CLIENT_CODE = os.getenv("CGI_BCREG_CLIENT_CODE", "112")
    CGI_EJV_SUPPLIER_NUMBER = os.getenv("CGI_EJV_SUPPLIER_NUMBER", "")

    IT_OPS_EMAIL = os.getenv("IT_OPS_EMAIL", "SBC_ITOperationsSupport@gov.bc.ca").split(",")
    DISABLE_EJV_ERROR_EMAIL = os.getenv("DISABLE_EJV_ERROR_EMAIL", "true").lower() == "true"
    DISABLE_CSV_ERROR_EMAIL = os.getenv("DISABLE_CSV_ERROR_EMAIL", "true").lower() == "true"
    DISABLE_AP_ERROR_EMAIL = os.getenv("DISABLE_AP_ERROR_EMAIL", "true").lower() == "true"

    # the day on which mail to get.put 1 to get mail next day of creation.put 2 to get mails day after tomorrow.
    NOTIFY_AFTER_DAYS = int(os.getenv("NOTIFY_AFTER_DAYS", 8))  # to get full 7 days tp pass, u need to put 8.

    # CGI FTP Configuration
    CGI_SFTP_HOST = os.getenv("CAS_SFTP_HOST", "localhost")
    CGI_SFTP_USERNAME = os.getenv("CGI_SFTP_USER_NAME")
    CGI_SFTP_PASSWORD = os.getenv("CGI_SFTP_PASSWORD")
    CGI_SFTP_VERIFY_HOST = os.getenv("SFTP_VERIFY_HOST", "True")
    CGI_SFTP_HOST_KEY = os.getenv("CAS_SFTP_HOST_KEY", "")
    CGI_SFTP_PORT = int(os.getenv("CAS_SFTP_PORT", 22))
    BCREG_CGI_FTP_PRIVATE_KEY_LOCATION = os.getenv(
        "BCREG_CGI_FTP_PRIVATE_KEY_LOCATION", "/payment-jobs/key/cgi_sftp_priv_key"
    )
    BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE = os.getenv("BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE")
    CGI_SFTP_DIRECTORY = os.getenv("CGI_SFTP_DIRECTORY", "/data")

    # CGI File specific configs
    CGI_TRIGGER_FILE_SUFFIX = os.getenv("CGI_TRIGGER_FILE_SUFFIX", "TRG")

    # disbursement delay
    DISBURSEMENT_DELAY_IN_DAYS = int(os.getenv("DISBURSEMENT_DELAY", 5))

    # CP Job variables
    CGI_AP_DISTRIBUTION = os.getenv("CGI_AP_DISTRIBUTION", "")
    CGI_AP_SUPPLIER_NUMBER = os.getenv("CGI_AP_SUPPLIER_NUMBER", "")
    CGI_AP_SUPPLIER_LOCATION = os.getenv("CGI_AP_SUPPLIER_LOCATION", "")
    CGI_AP_REMITTANCE_CODE = os.getenv("CGI_AP_REMITTANCE_CODE", "78")
    BCA_SUPPLIER_NUMBER = os.getenv("BCA_SUPPLIER_NUMBER", "")
    BCA_SUPPLIER_LOCATION = os.getenv("BCA_SUPPLIER_LOCATION", "")
    EFT_AP_DISTRIBUTION = os.getenv("EFT_AP_DISTRIBUTION", "")
    EFT_AP_SUPPLIER_LOCATION = os.getenv("EFT_AP_SUPPLIER_LOCATION", "")

    # FAS Client and secret
    CFS_FAS_CLIENT_ID = os.getenv("CFS_FAS_CLIENT_ID", "")
    CFS_FAS_CLIENT_SECRET = os.getenv("CFS_FAS_CLIENT_SECRET", "")

    # EFT variables
    EFT_TRANSFER_DESC = os.getenv("EFT_TRANSFER_DESC", "BCREGISTRIES {} {} EFT TRANSFER")
    EFT_OVERDUE_NOTIFY_EMAILS = os.getenv("EFT_OVERDUE_NOTIFY_EMAILS", "")

    # Google Cloud Storage settings
    GOOGLE_STORAGE_SA = os.getenv("GOOGLE_STORAGE_SA", "")
    GOOGLE_BUCKET_NAME = os.getenv("FTP_POLLER_BUCKET_NAME")  # FTP_POLLER_BUCKET_NAME
    GOOGLE_BUCKET_FOLDER_CGI_PROCESSING = os.getenv("GOOGLE_BUCKET_FOLDER_CGI_PROCESSING", "cgi_processing")
    GOOGLE_BUCKET_FOLDER_CGI_PROCESSED = os.getenv("GOOGLE_BUCKET_FOLDER_CGI_PROCESSED", "cgi_processed")
    GOOGLE_BUCKET_FOLDER_CGI_FEEDBACK = os.getenv("GOOGLE_BUCKET_FOLDER_CGI_FEEDBACK", "cgi_feedback")
    GOOGLE_BUCKET_FOLDER_AR = os.getenv("GOOGLE_BUCKET_FOLDER_AR", "ar")
    GOOGLE_BUCKET_FOLDER_EFT = os.getenv("GOOGLE_BUCKET_FOLDER_EFT", "eft")


class DevConfig(_Config):  # pylint: disable=too-few-public-methods
    TESTING = False
    DEBUG = True


class TestConfig(_Config):  # pylint: disable=too-few-public-methods
    """In support of testing only used by the py.test suite."""

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
        "postgresql+pg8000://{user}:{password}@{host}:{port}/{name}".format(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=int(DB_PORT),
            name=DB_NAME,
        ),
    )

    SERVER_NAME = "localhost:5001"

    AUTH_API_ENDPOINT = "http://localhost:8080/auth-api/"

    CFS_BASE_URL = "http://localhost:8080/paybc-api"
    CFS_CLIENT_ID = "TEST"
    CFS_CLIENT_SECRET = "TEST"
    USE_DOCKER_MOCK = os.getenv("USE_DOCKER_MOCK", None)

    PAYBC_DIRECT_PAY_CLIENT_ID = "abc"
    PAYBC_DIRECT_PAY_CLIENT_SECRET = "123"
    PAYBC_DIRECT_PAY_BASE_URL = "http://localhost:8080/paybc-api"
    PAYBC_DIRECT_PAY_REF_NUMBER = "123"

    DISABLE_AP_ERROR_EMAIL = False
    DISABLE_EJV_ERROR_EMAIL = False

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv("ACCOUNT_SECRET_KEY", "1234")

    # Setting values from the sftp docker container
    CGI_SFTP_VERIFY_HOST = "false"
    CGI_SFTP_USERNAME = "ftp_user"
    CGI_SFTP_PASSWORD = "ftp_pass"
    CGI_SFTP_PORT = 2222
    CGI_SFTP_DIRECTORY = "/data/"
    CGI_SFTP_HOST = "localhost"
    GCP_AUTH_KEY = None

    # Need a value for this, so we can mock the publish client.
    BUSINESS_PAY_TOPIC = "business-pay-topic"


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print("WARNING: SECRET_KEY being set as a one-shot", file=sys.stderr)

    TESTING = False
    DEBUG = False
