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
from unittest.mock import patch

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code, PaymentMethod, Role
from tests.utilities.base_test import (
    factory_payment_account,
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
    """GET /payment-links/{token} returns the invoice DTO for a valid token."""
    _enable_express_checkout()

    created = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=_express_checkout_headers(jwt),
    )
    token = created.json["paymentUrl"].rsplit("/", 1)[-1]

    user_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }
    rv = client.get(f"/api/v1/payment-links/{token}", headers=user_headers)
    assert rv.status_code == 200
    assert rv.json["id"] == created.json["id"]


def test_get_payment_link_rejects_unknown_token(session, client, jwt, app):
    """GET /payment-links/{token} returns 400 for an unknown token."""
    user_headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }
    rv = client.get("/api/v1/payment-links/does-not-exist", headers=user_headers)
    assert rv.status_code == 400


def test_redeem_binds_invoice_to_caller_account(session, client, jwt, app):
    """POST /payment-links/{token}/redemption rebinds the invoice from the SA adhoc account to the caller's."""
    _enable_express_checkout()
    target_account = factory_payment_account(auth_account_id="9999")
    target_account.save()

    # Create an express-checkout invoice via the SA path. It should land on the SA adhoc account
    # (sa-<azp>) — NOT on target_account yet, and the link row should be unclaimed.
    created = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=_express_checkout_headers(jwt),
    )
    token = created.json["paymentUrl"].rsplit("/", 1)[-1]
    invoice_id = created.json["id"]

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

    created = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=_express_checkout_headers(jwt),
    )
    token = created.json["paymentUrl"].rsplit("/", 1)[-1]

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
