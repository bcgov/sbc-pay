# Copyright © 2023 Province of British Columbia
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

"""Tests to verify the preflight requests on API end-points.

Test-Suite to ensure that the cors flight responses are working as expected.
"""


def test_preflight_fas_refund(app, client, jwt, session):
    """Assert preflight responses for fas refunds are correct."""
    rv = client.options(
        "/api/v1/fas/routing-slips/1/refunds",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")


def test_preflight_fas_routing_slip(app, client, jwt, session):
    """Assert preflight responses for fas routing slips are correct."""
    rv = client.options("/api/v1/fas/routing-slips", headers={"Access-Control-Request-Method": "POST"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")

    rv = client.options(
        "/api/v1/fas/routing-slips/queries",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")

    rv = client.options(
        "/api/v1/fas/routing-slips/2023-09-05/reports",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")

    rv = client.options("/api/v1/fas/routing-slips/1", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, PATCH")

    rv = client.options(
        "/api/v1/fas/routing-slips/1/links",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")

    rv = client.options(
        "/api/v1/fas/routing-slips/links",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")

    rv = client.options(
        "/api/v1/fas/routing-slips/1/comments",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")


def test_preflight_account(app, client, jwt, session):
    """Assert preflight responses for accounts are correct."""
    rv = client.options("/api/v1/accounts", headers={"Access-Control-Request-Method": "POST"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")

    rv = client.options("/api/v1/accounts/1", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "DELETE, GET, PUT")

    rv = client.options("/api/v1/accounts/1/fees", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "DELETE, GET, POST")

    rv = client.options(
        "/api/v1/accounts/1/fees/PRODUCT_CODE",
        headers={"Access-Control-Request-Method": "PUT"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "PUT")

    rv = client.options(
        "/api/v1/accounts/1/payments/queries",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")

    rv = client.options(
        "/api/v1/accounts/1/payments/reports",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")


def test_preflight_account_statements(app, client, jwt, session):
    """Assert preflight responses for account statements are correct."""
    rv = client.options(
        "/api/v1/accounts/1/statements",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")

    rv = client.options(
        "/api/v1/accounts/1/statements/1",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")


def test_preflight_account_statement_notifications(app, client, jwt, session):
    """Assert preflight responses for account statement notifications are correct."""
    rv = client.options(
        "/api/v1/accounts/1/statements/notifications",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")


def test_preflight_account_statement_settings(app, client, jwt, session):
    """Assert preflight responses for account statement settings are correct."""
    rv = client.options(
        "/api/v1/accounts/1/statements/settings",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")


def test_preflight_bank_accounts(app, client, jwt, session):
    """Assert preflight responses for bank accounts are correct."""
    rv = client.options(
        "/api/v1/bank-accounts/verifications",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")


def test_preflight_code(app, client, jwt, session):
    """Assert preflight responses for codes are correct."""
    rv = client.options("/api/v1/codes/CODETYPE", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")

    rv = client.options("/api/v1/codes/CODETYPE/CODE", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")


def test_preflight_distributions(app, client, jwt, session):
    """Assert preflight responses for distributions are correct."""
    rv = client.options("/api/v1/fees/distributions", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")

    rv = client.options("/api/v1/fees/distributions/1", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, PUT")

    rv = client.options(
        "/api/v1/fees/distributions/1/schedules",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")


def test_preflight_fee(app, client, jwt, session):
    """Assert preflight responses for fees are correct."""
    rv = client.options(
        "/api/v1/fees/COR_TYPE/FILING_TYPE_CODE",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")


def test_preflight_fee_schedule(app, client, jwt, session):
    """Assert preflight responses for fee schedule are correct."""
    rv = client.options("/api/v1/fees/schedules", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")


def test_preflight_invoice(app, client, jwt, session):
    """Assert preflight responses for invoice are correct."""
    rv = client.options("/api/v1/payment-requests", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")

    rv = client.options("/api/v1/payment-requests/1", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "DELETE, GET, PATCH")

    rv = client.options(
        "/api/v1/payment-requests/1/reports",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")


def test_preflight_invoice_receipt(app, client, jwt, session):
    """Assert preflight responses for invoice receipt are correct."""
    rv = client.options(
        "/api/v1/payment-requests/1/receipts",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")


def test_preflight_invoices(app, client, jwt, session):
    """Assert preflight responses for invoices are correct."""
    rv = client.options(
        "/api/v1/payment-requests/1/invoices",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")


def test_preflight_payment(app, client, jwt, session):
    """Assert preflight responses for payments are correct."""
    rv = client.options("/api/v1/accounts/1/payments", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, POST")


def test_preflight_refund(app, client, jwt, session):
    """Assert preflight responses for refund are correct."""
    rv = client.options(
        "/api/v1/payment-requests/1/refunds",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")


def test_preflight_eft_shortnames(app, client, jwt, session):
    """Assert preflight responses for eft shortnames are correct."""
    rv = client.options("/api/v1/eft-shortnames", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")

    rv = client.options("/api/v1/eft-shortnames/1", headers={"Access-Control-Request-Method": "GET"})
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, PATCH")

    rv = client.options(
        "/api/v1/eft-shortnames/summaries",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")

    rv = client.options(
        "/api/v1/eft-shortnames/1/links",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET, PATCH, POST")

    rv = client.options(
        "/api/v1/eft-shortnames/1/history",
        headers={"Access-Control-Request-Method": "GET"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "GET")

    rv = client.options(
        "/api/v1/eft-shortnames/1/payment",
        headers={"Access-Control-Request-Method": "POST"},
    )
    assert rv.status_code == 200
    assert_access_control_headers(rv, "*", "POST")


def assert_access_control_headers(rv, origins: str, methods: str):
    """Assert access control headers are correct."""
    assert rv.headers["Access-Control-Allow-Origin"] == origins
    assert rv.headers["Access-Control-Allow-Methods"] == methods
