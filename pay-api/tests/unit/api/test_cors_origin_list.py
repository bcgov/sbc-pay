# Copyright © 2026 Province of British Columbia
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

"""Tests probing the CORS_ORIGINS allow-list added in #2627, via the real config.py parsing path."""

import pytest

from pay_api.config import _get_config

LITERAL_ORIGINS_ENV_VALUE = (
    "https://app.bcregistry.gov.bc.ca,https://pay.bcregistry.gov.bc.ca,"
    "https://dev.pay.bcregistry.gov.bc.ca,https://partner.example.com"
)

SUBDOMAIN_WILDCARD_ORIGINS_ENV_VALUE = (
    r"^https://dev\.?.*\.bcregistry\.gov\.bc\.ca$,^https://[a-z0-9-]+\.pages\.example\.org$"
)

TOPLEVEL_WILDCARD_ORIGINS_ENV_VALUE = r"^https://(.*\.)?bcregistry\.gov\.bc\.ca$"

MIXED_ORIGINS_ENV_VALUE = (
    "https://app.bcregistry.gov.bc.ca,https://partner.example.com,"
    r"^https://dev\.?.*\.bcregistry\.gov\.bc\.ca$"
)


@pytest.fixture
def cors_origins_override(app, monkeypatch):
    """Override CORS_ORIGIN variable."""
    original = app.config.get("CORS_ORIGINS")

    def _apply(env_value):
        monkeypatch.setenv("CORS_ORIGINS", env_value)
        app.config["CORS_ORIGINS"] = [
            origin.strip() for origin in _get_config("CORS_ORIGINS", default="").split(",") if origin.strip()
        ]
        return app.config["CORS_ORIGINS"]

    yield _apply

    app.config["CORS_ORIGINS"] = original


@pytest.mark.parametrize(
    "origin",
    [
        "https://app.bcregistry.gov.bc.ca",
        "https://pay.bcregistry.gov.bc.ca",
        "https://dev.pay.bcregistry.gov.bc.ca",
        "https://partner.example.com",
    ],
)
def test_literal_config_origins(app, client, jwt, session, cors_origins_override, origin):
    """Assert literal whitelist urls for CORS_ORIGINS matches correctly."""
    cors_origins_override(LITERAL_ORIGINS_ENV_VALUE)

    rv = client.options(
        "/api/v1/documents",
        headers={"Access-Control-Request-Method": "GET", "Origin": origin},
    )
    assert rv.status_code == 200
    assert rv.headers.get("Access-Control-Allow-Origin") == origin
    assert rv.headers.get("Vary") == "Origin"


@pytest.mark.parametrize(
    "origin, should_match",
    [
        ("https://dev.bcregistry.gov.bc.ca", True),
        ("https://dev.pay.bcregistry.gov.bc.ca", True),
        ("https://dev.create.business.bcregistry.gov.bc.ca", True),
        ("https://dev.pages.example.org", True),
        ("https://dev.something.other.pages.example.org", False),
        ("https://pages.example.org", False),
        ("https://dev.pages.example.org.other.com", False),
    ],
)
def test_regex_config_origins_subdomain_wildcard(
    app, client, jwt, session, cors_origins_override, origin, should_match
):
    """Assert match pattern for mid url wildcard matches correctly."""
    cors_origins_override(SUBDOMAIN_WILDCARD_ORIGINS_ENV_VALUE)

    rv = client.options(
        "/api/v1/documents",
        headers={"Access-Control-Request-Method": "GET", "Origin": origin},
    )
    assert rv.status_code == 200
    if should_match:
        assert rv.headers.get("Access-Control-Allow-Origin") == origin
    else:
        assert "Access-Control-Allow-Origin" not in rv.headers


@pytest.mark.parametrize(
    "origin, should_match",
    [
        ("https://app.bcregistry.gov.bc.ca", True),
        ("https://partner.example.com", True),
        ("https://app.bcregistry.gov.bc.ca.other.com", False),
        ("https://dev.pay.bcregistry.gov.bc.ca", True),
        ("https://dev.create.business.bcregistry.gov.bc.ca", True),
        ("https://unrelated.example.com", False),
    ],
)
def test_mixed_origin_config(app, client, jwt, session, cors_origins_override, origin, should_match):
    """Assert mixing literal and regex config matches correctly."""
    cors_origins_override(MIXED_ORIGINS_ENV_VALUE)

    rv = client.options(
        "/api/v1/documents",
        headers={"Access-Control-Request-Method": "GET", "Origin": origin},
    )
    assert rv.status_code == 200
    if should_match:
        assert rv.headers.get("Access-Control-Allow-Origin") == origin
    else:
        assert "Access-Control-Allow-Origin" not in rv.headers


@pytest.mark.parametrize(
    "origin, should_match",
    [
        ("https://dev.pay.bcregistry.gov.bc.ca", True),
        ("https://test.bcregistry.gov.bc.ca", True),
        ("https://bcregistry.gov.bc.ca", True),
        ("https://something.other.test.bcregistry.gov.bc.ca", True),
        ("https://bcregistry.gov.bc.ca.other.com", False),
        ("https://bad.example.com", False),
    ],
)
def test_regex_config_origins_toplevel_wildcard(
    app, client, jwt, session, cors_origins_override, origin, should_match
):
    """A top-level wildcard covers any subdomain."""
    cors_origins_override(TOPLEVEL_WILDCARD_ORIGINS_ENV_VALUE)

    rv = client.options(
        "/api/v1/documents",
        headers={"Access-Control-Request-Method": "GET", "Origin": origin},
    )
    assert rv.status_code == 200
    if should_match:
        assert rv.headers.get("Access-Control-Allow-Origin") == origin
    else:
        assert "Access-Control-Allow-Origin" not in rv.headers


@pytest.mark.parametrize(
    "origin",
    [
        "https://anything.example",
        "http://localhost:3000",
    ],
)
def test_wildcard_origin_config(app, client, jwt, session, cors_origins_override, origin):
    """Assert CORS_ORIGINS allow all matches any origin."""
    cors_origins_override("*")

    rv = client.options(
        "/api/v1/documents",
        headers={"Access-Control-Request-Method": "GET", "Origin": origin},
    )
    assert rv.status_code == 200
    assert rv.headers.get("Access-Control-Allow-Origin") == origin
