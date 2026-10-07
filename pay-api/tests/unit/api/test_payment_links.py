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

"""Tests for the express-checkout invoice + payment-link endpoints."""

import json
from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import patch

import pytest
from requests.exceptions import HTTPError as RequestsHTTPError
from werkzeug.exceptions import Forbidden

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.services.payment_link import PaymentLinkService
from pay_api.services.receipt import Receipt as ReceiptService
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, Role
from tests.utilities.base_test import (
    factory_invoice_reference,
    factory_payment_account,
    factory_receipt,
    get_claims,
    get_payment_request,
    token_header,
)


def _enable_express_checkout(corp_type_code: str = "CP"):
    corp_type = CorpTypeModel.find_by_code(corp_type_code)
    corp_type.is_express_checkout_enabled = True
    corp_type.save()
    # Bust the CorpType dump populated at app startup so CodeService picks up the new flag.
    cache.delete(Code.CORP_TYPE.value)


def _express_checkout_headers(jwt, azp: str = "partner-client"):
    token = jwt.create_jwt(
        get_claims(role=Role.CREATE_EXPRESS_CHECKOUT_INVOICE.value, azp=azp),
        token_header,
    )
    return {"Authorization": f"Bearer {token}", "content-type": "application/json"}


# Matches the URLs already whitelisted by TestConfig.VALID_REDIRECT_URLS — DIRECT_PAY
# invoices have their clientSystemUrl checked against that list.
TRANSACTION_BODY = {
    "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
    "payReturnUrl": "http://localhost:8080/pay-web",
}

RECEIPT_BODY = {"filingDateTime": "June 27, 2019", "fileName": "payment_receipt"}


def _settle_invoice(invoice_id: int):
    """Put an invoice in the state a completed card payment leaves it in.

    A receipt can only be rendered from a settled invoice: `Receipt.get_receipt_details`
    reads the receipt row and the COMPLETED invoice reference, both written by the
    payment reconciliation. Flipping the status alone isn't enough.
    """
    invoice = InvoiceModel.find_by_id(invoice_id)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_date = datetime.now(tz=UTC)
    invoice.paid = invoice.total
    invoice.save()
    factory_invoice_reference(invoice_id, status_code=InvoiceReferenceStatus.COMPLETED.value).save()
    factory_receipt(invoice_id, receipt_amount=float(invoice.total)).save()


def _create_express_checkout_invoice(client, jwt, extra_body: dict = None):
    """Create an express-checkout invoice and return (token, invoice_id)."""
    body = {**get_payment_request(), **(extra_body or {})}
    created = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(body),
        headers=_express_checkout_headers(jwt),
    )
    assert created.status_code == 201
    return created.json["paymentUrl"].rsplit("/", 1)[-1], created.json["id"]


def test_create_express_checkout_invoice_returns_payment_url(session, client, jwt, app):
    """POST /payment-requests with the express-checkout role returns a 201 + paymentUrl."""
    _enable_express_checkout()

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=_express_checkout_headers(jwt),
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentUrl")
    assert rv.json.get("paymentUrl").rsplit("/", 1)[-1]  # token appended


def test_create_express_checkout_invoice_stores_email_and_return_url(session, client, jwt, app):
    """Email and returnUrl in the creation request are persisted on the payment link row."""
    _enable_express_checkout()
    _, invoice_id = _create_express_checkout_invoice(
        client, jwt, extra_body={"email": "payer@example.com", "returnUrl": "http://localhost:8080/done"}
    )

    link = InvoicePaymentLinkModel.query.filter_by(invoice_id=invoice_id).one()
    assert link.email == "payer@example.com"
    assert link.return_url == "http://localhost:8080/done"


def test_create_express_checkout_invoice_rejects_unlisted_return_url(session, client, jwt, app):
    """POST /payment-requests returns 400 when returnUrl is not in VALID_REDIRECT_URLS."""
    _enable_express_checkout()

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps({**get_payment_request(), "returnUrl": "https://evil.example.com/steal"}),
        headers=_express_checkout_headers(jwt),
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == "INVALID_REDIRECT_URI"


def test_create_express_checkout_invoice_rejected_when_corp_type_disabled(session, client, jwt, app):
    """POST /payment-requests returns 400 EXPRESS_CHECKOUT_NOT_ENABLED for a corp type without the flag."""
    # No _enable_express_checkout — CP corp type is disabled by default.
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=_express_checkout_headers(jwt),
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == "EXPRESS_CHECKOUT_NOT_ENABLED"


def test_get_payment_link_returns_invoice(session, client, jwt, app):
    """GET /payment-links/{token} returns the invoice DTO including returnUrl for a valid token."""
    _enable_express_checkout()
    token, invoice_id = _create_express_checkout_invoice(
        client, jwt, extra_body={"returnUrl": "http://localhost:8080/done"}
    )

    user_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }
    rv = client.get(f"/api/v1/payment-links/{token}", headers=user_headers)
    assert rv.status_code == 200
    assert rv.json["id"] == invoice_id
    assert rv.json["returnUrl"] == "http://localhost:8080/done"
    # This route is open to anyone holding the link — the adhoc SA account the unredeemed
    # invoice is parked on is internal routing and must not be handed out.
    assert rv.json["paymentAccount"]["accountId"] is None


def test_get_payment_link_rejects_unknown_token(session, client, jwt, app):
    """GET /payment-links/{token} returns 400 for an unknown token."""
    user_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }
    rv = client.get("/api/v1/payment-links/does-not-exist", headers=user_headers)
    assert rv.status_code == 400


@pytest.mark.parametrize("auth_exc", [RequestsHTTPError(), Forbidden()])
def test_get_payment_link_claimed_by_other_account_returns_400(session, client, jwt, app, auth_exc):
    """GET /payment-links/{token} returns 400 (not 500) when auth check fails for a claimed link.

    Covers both paths: auth-api returning 4xx (RequestsHTTPError) and
    auth-api returning empty roles causing abort(403) (WerkzeugHTTPException).
    """
    _enable_express_checkout()
    token, _ = _create_express_checkout_invoice(client, jwt)

    # Redeem the link so linked_at is set — GET will now run the auth check.
    first_account = factory_payment_account(auth_account_id="1111")
    first_account.save()
    auth_response = {"account": {"id": "1111", "paymentInfo": {"methodOfPayment": PaymentMethod.DIRECT_PAY.value}}}
    redeem_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
        "Account-Id": "1111",
    }
    with patch("pay_api.services.payment_link.check_auth", return_value=auth_response):
        assert client.post(f"/api/v1/payment-links/{token}/redemption", headers=redeem_headers).status_code == 200

    # Simulate the auth check failing for a different caller.
    get_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
        "Account-Id": "9999",
    }
    with patch("pay_api.services.payment_link.InvoiceService.find_by_id", side_effect=auth_exc):
        rv = client.get(f"/api/v1/payment-links/{token}", headers=get_headers)

    assert rv.status_code == 400


def test_redeem_binds_invoice_to_caller_account(session, client, jwt, app):
    """POST /payment-links/{token}/redemption rebinds the invoice from the SA adhoc account to the caller's."""
    _enable_express_checkout()
    target_account = factory_payment_account(auth_account_id="9999")
    target_account.save()

    # Create an express-checkout invoice via the SA path. It should land on the SA adhoc account
    # (sa-<azp>) — NOT on target_account yet, and the link row should be unclaimed.
    token, invoice_id = _create_express_checkout_invoice(client, jwt)

    # Initial state: on the SA adhoc account, link row exists but unclaimed.
    initial_invoice = InvoiceService.find_by_id(invoice_id, skip_auth_check=True)
    sa_account = PaymentAccountModel.find_by_auth_account_id("sa-partner-client")
    assert sa_account is not None
    assert initial_invoice.payment_account_id == sa_account.id
    assert initial_invoice.payment_account_id != target_account.id
    initial_link = InvoicePaymentLinkModel.find_by_token(token)
    assert initial_link is not None
    assert initial_link.linked_at is None

    # Redeem: caller is on target_account (Account-Id header 9999). Link binds invoice to their account.
    user_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
        "Account-Id": "9999",
    }
    auth_response = {"account": {"id": "9999", "paymentInfo": {"methodOfPayment": PaymentMethod.DIRECT_PAY.value}}}
    with patch("pay_api.services.payment_link.check_auth", return_value=auth_response):
        rv = client.post(f"/api/v1/payment-links/{token}/redemption", headers=user_headers)

    # Post-redemption: invoice moved to target_account, link row stamped as consumed.
    assert rv.status_code == 200
    bound_invoice = InvoiceService.find_by_id(invoice_id, skip_auth_check=True)
    assert bound_invoice.payment_account_id == target_account.id
    consumed_link = InvoicePaymentLinkModel.find_by_token(token)
    assert consumed_link.linked_at is not None


def test_redeem_rejects_second_account(session, client, jwt, app):
    """A second, different account trying to redeem an already-linked token gets a uniform 400."""
    _enable_express_checkout()
    first_account = factory_payment_account(auth_account_id="1111")
    first_account.save()
    second_account = factory_payment_account(auth_account_id="2222")
    second_account.save()

    token, _ = _create_express_checkout_invoice(client, jwt)

    def _redeem_as(account_id: str):
        headers = {
            "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
            "content-type": "application/json",
            "Account-Id": account_id,
        }
        auth_response = {
            "account": {"id": account_id, "paymentInfo": {"methodOfPayment": PaymentMethod.DIRECT_PAY.value}}
        }
        with patch("pay_api.services.payment_link.check_auth", return_value=auth_response):
            return client.post(f"/api/v1/payment-links/{token}/redemption", headers=headers)

    assert _redeem_as("1111").status_code == 200
    assert _redeem_as("2222").status_code == 400


def test_redeem_rejects_nsf_account(session, client, jwt, app):
    """Redemption is blocked, with the specific PAD_CURRENTLY_NSF type, for an NSF-suspended account."""
    _enable_express_checkout()
    target_account = factory_payment_account(
        auth_account_id="9999",
        payment_method_code=PaymentMethod.PAD.value,
        has_nsf_invoices=datetime.now(tz=UTC),
    )
    target_account.save()
    token, _ = _create_express_checkout_invoice(client, jwt)

    user_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
        "Account-Id": "9999",
    }
    auth_response = {"account": {"id": "9999", "paymentInfo": {"methodOfPayment": PaymentMethod.PAD.value}}}
    with patch("pay_api.services.payment_link.check_auth", return_value=auth_response):
        rv = client.post(f"/api/v1/payment-links/{token}/redemption", headers=user_headers)

    assert rv.status_code == 400
    assert rv.json["type"] == "PAD_CURRENTLY_NSF"
    # The invoice must not have been rebound - the blocker fires before that happens.
    assert InvoicePaymentLinkModel.find_by_token(token).linked_at is None


def test_transaction_without_login_returns_pay_system_url(session, client, jwt, app):
    """POST /payment-links/{token}/transactions starts a transaction with no Authorization header.

    This is the whole point of the route — an anonymous payer holding the link can reach
    PayBC without signing in, and the invoice stays on the SA account while they do.
    """
    _enable_express_checkout()
    token, invoice_id = _create_express_checkout_invoice(client, jwt)

    rv = client.post(
        f"/api/v1/payment-links/{token}/transactions",
        data=json.dumps(TRANSACTION_BODY),
        headers={"content-type": "application/json"},  # deliberately no Authorization
    )

    assert rv.status_code == 201
    assert rv.json.get("paySystemUrl")

    # The payer never redeemed, so the invoice is still parked on the SA adhoc account.
    sa_account = PaymentAccountModel.find_by_auth_account_id("sa-partner-client")
    assert InvoiceService.find_by_id(invoice_id, skip_auth_check=True).payment_account_id == sa_account.id


def test_transaction_rejects_unknown_token(session, client, jwt, app):
    """An unknown token gets the same 400 as any other failure — no enumeration signal."""
    rv = client.post(
        "/api/v1/payment-links/does-not-exist/transactions",
        data=json.dumps(TRANSACTION_BODY),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400


def test_transaction_rejects_disallowed_redirect_url(session, client, jwt, app):
    """Redirect URLs are still checked against VALID_REDIRECT_URLS on this route.

    Guards the delegation to TransactionService — if this route ever stopped going through
    it, an open redirect would slip in silently.
    """
    _enable_express_checkout()
    token, _ = _create_express_checkout_invoice(client, jwt)

    rv = client.post(
        f"/api/v1/payment-links/{token}/transactions",
        data=json.dumps({**TRANSACTION_BODY, "clientSystemUrl": "http://evil.example.com/steal"}),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400


def test_receipt_without_login_returns_pdf(session, client, jwt, app):
    """POST /payment-links/{token}/receipts issues the receipt with no Authorization header.

    a guest who paid by card has no session, and the link is their only route to a receipt: no account, no email.
    """
    _enable_express_checkout()
    token, invoice_id = _create_express_checkout_invoice(client, jwt)
    _settle_invoice(invoice_id)

    with patch("pay_api.services.receipt.get_service_account_token", return_value="sa-token"):
        rv = client.post(
            f"/api/v1/payment-links/{token}/receipts",
            data=json.dumps(RECEIPT_BODY),
            headers={"content-type": "application/json"},
        )

    assert rv.status_code == 201
    assert rv.headers["Content-Type"] == "application/pdf"


def test_receipt_rejects_unpaid_invoice(session, client, jwt, app):
    """Nothing to receipt before payment — the pre-payment document is /reports."""
    _enable_express_checkout()
    token, _ = _create_express_checkout_invoice(client, jwt)

    rv = client.post(
        f"/api/v1/payment-links/{token}/receipts",
        data=json.dumps(RECEIPT_BODY),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400


def test_receipt_omits_the_adhoc_service_account(session, client, jwt, app):
    """An anonymous payer's receipt must not print the internal `sa-<client_id>` account."""
    _enable_express_checkout()
    _, invoice_id = _create_express_checkout_invoice(client, jwt)
    _settle_invoice(invoice_id)

    details = ReceiptService.get_receipt_details({}, invoice_id, skip_auth_check=True)

    assert details["invoice"]["paymentAccount"]["accountId"] is None


def test_receipt_keeps_the_account_once_the_link_is_redeemed(session, client, jwt, app):
    """A redeemed link means a real account owns the invoice — that one belongs on the receipt."""
    _enable_express_checkout()
    _, invoice_id = _create_express_checkout_invoice(client, jwt)
    _settle_invoice(invoice_id)

    # Stand the invoice on a real (numeric) account and consume the link, as redemption does.
    real_account = factory_payment_account(auth_account_id="9999")
    real_account.save()
    invoice = InvoiceModel.find_by_id(invoice_id)
    invoice.payment_account_id = real_account.id
    invoice.save()
    PaymentLinkService.mark_linked(InvoicePaymentLinkModel.query.filter_by(invoice_id=invoice_id).one())

    details = ReceiptService.get_receipt_details({}, invoice_id, skip_auth_check=True)

    assert details["invoice"]["paymentAccount"]["accountId"] == "9999"


def test_payment_links_disabled_by_flag(session, client, jwt, app):
    """Assert that all payment link endpoints return 501 when disable-payment-links flag is on."""
    _enable_express_checkout()
    token, _ = _create_express_checkout_invoice(client, jwt)

    with patch("pay_api.resources.v1.payment_links.flags.is_on", return_value=True):
        assert client.get(f"/api/v1/payment-links/{token}").status_code == HTTPStatus.NOT_IMPLEMENTED
        assert (
            client.post(
                f"/api/v1/payment-links/{token}/transactions",
                data=json.dumps(TRANSACTION_BODY),
                headers={"content-type": "application/json"},
            ).status_code
            == HTTPStatus.NOT_IMPLEMENTED
        )
        assert (
            client.post(
                f"/api/v1/payment-links/{token}/receipts",
                data=json.dumps(RECEIPT_BODY),
                headers={"content-type": "application/json"},
            ).status_code
            == HTTPStatus.NOT_IMPLEMENTED
        )
        assert client.post(f"/api/v1/payment-links/{token}/redemption").status_code == HTTPStatus.NOT_IMPLEMENTED
