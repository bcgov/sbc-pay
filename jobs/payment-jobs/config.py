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
    CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', 10))
    GENERATE_RANDOM_INVOICE_NUMBER = os.getenv('CFS_GENERATE_RANDOM_INVOICE_NUMBER', 'False')

    # legislative timezone for future effective dating
    LEGISLATIVE_TIMEZONE = os.getenv('LEGISLATIVE_TIMEZONE', 'America/Vancouver')

    # notify-API URL
    NOTIFY_API_URL = os.getenv('NOTIFY_API_URL')

    # Service account details
    KEYCLOAK_SERVICE_ACCOUNT_ID = os.getenv('SBC_AUTH_ADMIN_CLIENT_ID')
    KEYCLOAK_SERVICE_ACCOUNT_SECRET = os.getenv('SBC_AUTH_ADMIN_CLIENT_SECRET')

    # JWT_OIDC Settings
    JWT_OIDC_ISSUER = os.getenv('JWT_OIDC_ISSUER')

    # Front end url
    AUTH_WEB_URL = os.getenv('AUTH_WEB_PAY_TRANSACTION_URL', '')
    AUTH_WEB_STATEMENT_URL = os.getenv('AUTH_WEB_STATEMENT_URL', 'account/orgId/settings/statements')
    REGISTRIES_LOGO_IMAGE_NAME = os.getenv('REGISTRIES_LOGO_IMAGE_NAME', 'bc_logo_for_email.png')

    # NATS Config
    NATS_SERVERS = os.getenv('NATS_SERVERS', 'nats://127.0.0.1:4222').split(',')
    NATS_CLUSTER_ID = os.getenv('NATS_CLUSTER_ID', 'test-cluster')

    # NATS Config for account events
    NATS_ACCOUNT_CLIENT_NAME = os.getenv('NATS_ACCOUNT_CLIENT_NAME', 'account.events.worker')
    NATS_ACCOUNT_SUBJECT = os.getenv('NATS_ACCOUNT_SUBJECT', 'account.events')

    # NATS Config for transaction events
    NATS_PAYMENT_CLIENT_NAME = os.getenv('NATS_PAYMENT_CLIENT_NAME', 'entity.filing.payment.worker')
    NATS_PAYMENT_SUBJECT = os.getenv('NATS_PAYMENT_SUBJECT', 'entity.filing.payment')

    # Auth API Endpoint
    AUTH_API_ENDPOINT = f'{os.getenv("AUTH_API_URL")}/'

    CFS_ACCOUNT_DESCRIPTION = os.getenv('CFS_ACCOUNT_DESCRIPTION', 'BCR')
    CFS_INVOICE_PREFIX = os.getenv('CFS_INVOICE_PREFIX', 'REG')
    CFS_STOP_PAD_ACCOUNT_CREATION = os.getenv('CFS_STOP_PAD_ACCOUNT_CREATION', 'false').lower() == 'true'
    CFS_PARTY_PREFIX = os.getenv('CFS_PARTY_PREFIX', 'BCR-')

    CFS_INVOICE_CUT_OFF_HOURS_UTC = int(os.getenv('CFS_INVOICE_CUT_OFF_HOURS_UTC', '2'))
    CFS_INVOICE_CUT_OFF_MINUTES_UTC = int(os.getenv('CFS_INVOICE_CUT_OFF_MINUTES_UTC', '0'))

    SENTRY_DSN = os.getenv('SENTRY_DSN', None)

    # The number of characters which can be exposed to admins for a bank account number
    MASK_LEN = int(os.getenv('MASK_LEN', 3))

    TESTING = False
    DEBUG = True
    PAD_CONFIRMATION_PERIOD_IN_DAYS = int(os.getenv('PAD_CONFIRMATION_PERIOD_IN_DAYS', '3'))

    NATS_MAILER_CLIENT_NAME = os.getenv('NATS_MAILER_CLIENT_NAME', 'account.mailer.worker')
    NATS_MAILER_SUBJECT = os.getenv('NATS_MAILER_SUBJECT', 'account.mailer')

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY')

    # EJV config variables
    CGI_FEEDER_NUMBER = os.getenv('CGI_FEEDER_NUMBER')
    CGI_MINISTRY_PREFIX = os.getenv('CGI_MINISTRY_PREFIX')
    CGI_DISBURSEMENT_DESC = os.getenv('CGI_DISBURSEMENT_DESC', 'BCREGISTRIES {} {} DISBURSEMENTS')
    CGI_MESSAGE_VERSION = os.getenv('CGI_MESSAGE_VERSION', '4010')
    CGI_BCREG_CLIENT_CODE = os.getenv('CGI_BCREG_CLIENT_CODE', '112')

    # Minio configuration values
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
    MINIO_ACCESS_SECRET = os.getenv('MINIO_ACCESS_SECRET')
    MINIO_BUCKET_NAME = os.getenv('MINIO_EJV_BUCKET_NAME', 'cgi-ejv')
    MINIO_SECURE = True

    # the day on which mail to get.put 1 to get mail next day of creation.put 2 to get mails day after tomorrow.
    NOTIFY_AFTER_DAYS = int(os.getenv('NOTIFY_AFTER_DAYS', 8))  # to get full 7 days tp pass, u need to put 8.

    # CGI FTP Configuration
    CGI_SFTP_HOST = os.getenv('CAS_SFTP_HOST', 'localhost')
    CGI_SFTP_USERNAME = os.getenv('CGI_SFTP_USER_NAME')
    CGI_SFTP_PASSWORD = os.getenv('CGI_SFTP_PASSWORD')
    CGI_SFTP_VERIFY_HOST = os.getenv('SFTP_VERIFY_HOST', 'True')
    CGI_SFTP_HOST_KEY = os.getenv('CAS_SFTP_HOST_KEY', '')
    CGI_SFTP_PORT = int(os.getenv('CAS_SFTP_PORT', 22))
    BCREG_CGI_FTP_PRIVATE_KEY_LOCATION = os.getenv('BCREG_CGI_FTP_PRIVATE_KEY_LOCATION',
                                                   '/payment-jobs/key/cgi_sftp_priv_key')
    BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE = os.getenv('BCREG_CGI_FTP_PRIVATE_KEY_PASSPHRASE')
    CGI_SFTP_DIRECTORY = os.getenv('CGI_SFTP_DIRECTORY', '/data')

    # CGI File specific configs
    CGI_TRIGGER_FILE_SUFFIX = os.getenv('CGI_TRIGGER_FILE_SUFFIX', 'TRG')

    HOLIDAYS_LIST = os.getenv('HOLIDAYS_LIST', default='2021-Jan-01,2021-Feb-15,2021-Apr-02,2021-May-24,2021-Jul-1, '
                                                       '2021-Jul-1, 2021-Aug-2, 2021-Sep-6,2021-Oct-11, 2021-Nov-11, '
                                                       '2021-Dec-25')

    # disbursement delay
    DISBURSEMENT_DELAY_IN_DAYS = int(os.getenv('DISBURSEMENT_DELAY', 5))

    # Is FAS-CFS integration disabled
    DISABLE_CFS_FAS_INTEGRATION = os.getenv('DISABLE_CFS_FAS_INTEGRATION', 'false').lower() == 'true'

    # CP Job variables
    CGI_AP_DISTRIBUTION = os.getenv('CGI_AP_DISTRIBUTION', '')
    CGI_AP_SUPPLIER_NUMBER = os.getenv('CGI_AP_SUPPLIER_NUMBER', '')
    CGI_AP_SUPPLIER_LOCATION = os.getenv('CGI_AP_SUPPLIER_LOCATION', '')
    CGI_AP_DISTRIBUTION_VENDOR_NUMBER = os.getenv('CGI_AP_DISTRIBUTION_VENDOR_NUMBER', '')


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

    AUTH_API_ENDPOINT = 'http://localhost:8080/auth-api/'

    CFS_BASE_URL = 'http://localhost:8080/paybc-api'
    CFS_CLIENT_ID = 'TEST'
    CFS_CLIENT_SECRET = 'TEST'
    USE_DOCKER_MOCK = os.getenv('USE_DOCKER_MOCK', None)

    # Secret key for encrypting bank account
    ACCOUNT_SECRET_KEY = os.getenv('ACCOUNT_SECRET_KEY', '1234')

    # Setting values from the sftp docker container
    CGI_SFTP_VERIFY_HOST = 'false'
    CGI_SFTP_USERNAME = 'ftp_user'
    CGI_SFTP_PASSWORD = 'ftp_pass'
    CGI_SFTP_PORT = 2222
    CGI_SFTP_DIRECTORY = '/data/'
    CGI_SFTP_HOST = 'localhost'


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = os.getenv('SECRET_KEY', None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print('WARNING: SECRET_KEY being set as a one-shot', file=sys.stderr)

    TESTING = False
    DEBUG = False
