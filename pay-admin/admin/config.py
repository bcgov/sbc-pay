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

import json
import os
import sys

from cachelib.file import FileSystemCache
from dotenv import find_dotenv, load_dotenv

# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())

CONFIGURATION = {
    "development": "admin.config.DevConfig",
    "testing": "admin.config.TestConfig",
    "production": "admin.config.ProdConfig",
    "default": "admin.config.ProdConfig",
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
    else:
        raise KeyError(f"Unknown configuration '{config_name}'")
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

    SECRET_KEY = "my secret"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # POSTGRESQL
    DB_USER = _get_config("DATABASE_USERNAME")
    DB_PASSWORD = _get_config("DATABASE_PASSWORD")
    DB_NAME = _get_config("DATABASE_NAME")
    DB_HOST = _get_config("DATABASE_HOST")
    DB_PORT = _get_config("DATABASE_PORT", default="5432")
    if DB_UNIX_SOCKET := os.getenv("DATABASE_UNIX_SOCKET", None):
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?unix_sock={DB_UNIX_SOCKET}/.s.PGSQL.5432"
        )
    else:
        SQLALCHEMY_DATABASE_URI = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"
    SQLALCHEMY_ECHO = _get_config("SQLALCHEMY_ECHO", default="False").lower() == "true"

    # Normal Keycloak parameters.
    # Backwards compat for OCP and GCP.
    OIDC_CLIENT_SECRETS = os.getenv("PAY_OIDC_CLIENT_SECRETS", "secrets/keycloak.json")
    if not os.path.isfile(OIDC_CLIENT_SECRETS):
        OIDC_CLIENT_SECRETS = json.loads(OIDC_CLIENT_SECRETS)
    OIDC_SCOPES = ["openid", "email", "profile"]
    # Undocumented Keycloak parameter: allows sending cookies without the secure flag, which we need for the local
    # non-TLS HTTP server. Set this to non-"True" for local development, and use the default everywhere else.
    OIDC_ID_TOKEN_COOKIE_SECURE = os.getenv("PAY_OIDC_ID_TOKEN_COOKIE_SECURE", "True").lower() == "true"

    PREFERRED_URL_SCHEME = "https"
    SESSION_TYPE = "cachelib"
    SESSION_SERIALIZATION_FORMAT = "json"
    SESSION_CACHELIB = FileSystemCache(threshold=500, cache_dir="/tmp/sessions")
    CACHE_TYPE = "simple"

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

    # POSTGRESQL
    DB_USER = _get_config("DATABASE_TEST_USERNAME", default="postgres")
    DB_PASSWORD = _get_config("DATABASE_TEST_PASSWORD", default="postgres")
    DB_NAME = _get_config("DATABASE_TEST_NAME", default="paytestdb")
    DB_HOST = _get_config("DATABASE_TEST_HOST", default="localhost")
    DB_PORT = _get_config("DATABASE_TEST_PORT", default="5432")
    SQLALCHEMY_DATABASE_URI = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}"


class ProdConfig(_Config):  # pylint: disable=too-few-public-methods
    """Production environment configuration."""

    SECRET_KEY = _get_config("SECRET_KEY", default=None)

    if not SECRET_KEY:
        SECRET_KEY = os.urandom(24)
        print("WARNING: SECRET_KEY being set as a one-shot", file=sys.stderr)

    TESTING = False
    DEBUG = False
