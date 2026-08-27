"""Tests to verify CORS headers on error responses.

sbc_common_components.ExceptionHandler sets a wildcard Access-Control-Allow-Origin
unconditionally on error responses (401/404/etc.) before pay-api's own after_request
hook runs. Ensure that wildcard never survives for a non-matching or missing Origin.
"""

import pytest

REAL_ORIGIN = "https://dev.pay.bcregistry.gov.bc.ca"


@pytest.fixture
def cors_origins_override(app):
    """Scope a CORS_ORIGINS override to this file, restoring it after each test."""
    original = app.config.get("CORS_ORIGINS")
    app.config["CORS_ORIGINS"] = [REAL_ORIGIN]
    yield
    app.config["CORS_ORIGINS"] = original


def test_malicious_origin_gets_no_header_on_401(app, client, jwt, session, cors_origins_override):
    """Assert a non-matching origin gets no CORS header on a 401 response."""
    rv = client.get("/api/v1/fees/BC/BCINC", headers={"Origin": "https://evil-attacker-site.ru"})
    assert rv.status_code == 401
    assert "Access-Control-Allow-Origin" not in rv.headers


def test_no_origin_gets_no_header_on_401(app, client, jwt, session, cors_origins_override):
    """Assert a missing origin gets no CORS header on a 401 response."""
    rv = client.get("/api/v1/fees/BC/BCINC")
    assert rv.status_code == 401
    assert "Access-Control-Allow-Origin" not in rv.headers


def test_malicious_origin_gets_no_header_on_404(app, client, jwt, session, cors_origins_override):
    """Assert a non-matching origin gets no CORS header on a 404 response."""
    rv = client.get("/api/v1/this-route-does-not-exist", headers={"Origin": "https://evil-attacker-site.ru"})
    assert rv.status_code == 404
    assert "Access-Control-Allow-Origin" not in rv.headers


def test_real_origin_still_gets_correct_header_on_401(app, client, jwt, session, cors_origins_override):
    """Assert a matching origin still gets echoed back correctly on a 401 response."""
    rv = client.get("/api/v1/fees/BC/BCINC", headers={"Origin": REAL_ORIGIN})
    assert rv.status_code == 401
    assert rv.headers.get("Access-Control-Allow-Origin") == REAL_ORIGIN
