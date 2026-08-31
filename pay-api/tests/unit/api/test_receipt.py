# Copyright © 2024 Province of British Columbia
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

"""Tests to assure the receipt end-point.

Test-Suite to ensure that the /receipt endpoint is working as expected.
"""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from flask import abort

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.enums import PaymentMethod, Role
from tests.utilities.base_test import (
    factory_invoice,
    factory_payment_account,
    get_claims,
    get_payment_request,
    get_payment_request_with_no_contact_info,
    get_unlinked_pad_account_payload,
    get_zero_dollar_payment_request,
    token_header,
)


@pytest.fixture
def run_around_tests(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    assert rv.status_code == 201


def test_receipt_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    pay_id = rv.json.get("id")

    payment_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{payment_id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    rv = client.patch(
        f"/api/v1/payment-requests/{payment_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )

    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{pay_id}/receipts",
        data=json.dumps(filing_data),
        headers=headers,
    )
    assert rv.status_code == 201


def test_receipt_creation_with_invoice(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inovice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{inovice_id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    client.patch(
        f"/api/v1/payment-requests/{inovice_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )
    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{inovice_id}/receipts",
        data=json.dumps(filing_data),
        headers=headers,
    )
    assert rv.status_code == 201


def test_create_pad_payment_receipt(session, client, jwt, app):
    """Assert payment request works for PAD accounts."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Create account first
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_unlinked_pad_account_payload(account_id=1234)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    # Update the payment account as ACTIVE
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    payment_account.pad_activation_date = datetime.now(tz=UTC)
    payment_account.save()
    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_payment_method(
        payment_account.id, PaymentMethod.PAD.value
    )
    cfs_account.status = "ACTIVE"
    cfs_account.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_no_contact_info(
                corp_type="BEN",
                filing_type_code="BCINC",
                payment_method=PaymentMethod.PAD.value,
            )
        ),
        headers=headers,
    )
    assert rv.json.get("paymentMethod") == PaymentMethod.PAD.value

    inv_id = rv.json.get("id")
    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }

    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/receipts",
        data=json.dumps(filing_data),
        headers=headers,
    )
    assert rv.status_code == 201


def test_receipt_creation_with_invalid_request(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    redirect_uri = "http%3A//localhost%3A8080/coops-web/transactions%3Ftransaction_id%3Dabcd"
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions?redirect_uri={redirect_uri}",
        data=json.dumps({}),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )
    filing_data = {"corpName": "CP0001234"}
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/receipts",
        data=json.dumps(filing_data),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == "INVALID_REQUEST"


def test_receipt_creation_with_invalid_identifiers(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    invoice_id = 2222
    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/receipts",
        data=json.dumps(filing_data),
        headers=headers,
    )
    assert rv.status_code == 400


def test_receipt_creation_for_internal_payments(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_zero_dollar_payment_request()),
        headers=headers,
    )
    pay_id = rv.json.get("id")

    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{pay_id}/receipts",
        data=json.dumps(filing_data),
        headers=headers,
    )
    assert rv.status_code == 201


def test_get_receipt(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inovice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{inovice_id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    client.patch(
        f"/api/v1/payment-requests/{inovice_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )

    pay_receipt = client.get(f"/api/v1/payment-requests/{inovice_id}/receipts", headers=headers)
    assert pay_receipt.status_code == 200


def _authorize_via_linking_key_only(business_identifier, account_id=None, **kwargs):  # noqa: ARG001
    """Mock check_auth: authorize only when called via the business-identifier/linking-key branch."""
    if account_id is None:
        return {"roles": ["edit", "view", "make_payment"]}
    abort(403)


def test_post_receipt_linking_key_allows_business_filing_access(session, client, jwt, app):
    """Assert a linking-key can generate a receipt PDF for a business-filing invoice."""
    vendor_account = factory_payment_account(auth_account_id="VENDOR_777")
    vendor_account.save()
    invoice = factory_invoice(
        payment_account=vendor_account,
        business_identifier="CP0001234",
        payment_method_code=PaymentMethod.PAD.value,
    )
    invoice.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Linking-Key": "test-linking-key",
    }
    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }

    with patch("pay_api.services.invoice.check_auth", side_effect=_authorize_via_linking_key_only) as mock_check_auth:
        rv = client.post(
            f"/api/v1/payment-requests/{invoice.id}/receipts",
            data=json.dumps(filing_data),
            headers=headers,
        )

    assert rv.status_code == 201

    mock_check_auth.assert_called_once()
    called_args, called_kwargs = mock_check_auth.call_args
    assert called_args[0] == "CP0001234"  # business_identifier
    assert called_kwargs.get("account_id") is None
    assert called_kwargs.get("one_of_roles") == ALL_ALLOWED_ROLES


def test_post_receipt_linking_key_denied_for_non_business_invoice(session, client, jwt, app):
    """Assert a linking key does not grant access to generate a receipt for a non-business-filing invoice."""
    owner_account = factory_payment_account(auth_account_id="OWNER_999")
    owner_account.save()
    invoice = factory_invoice(
        payment_account=owner_account,
        business_identifier=None,
        payment_method_code=PaymentMethod.PAD.value,
    )
    invoice.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Linking-Key": "test-linking-key",
    }
    filing_data = {
        "corpName": "CP0001234",
        "filingDateTime": "June 27, 2019",
        "fileName": "director-change",
    }

    with patch("pay_api.services.invoice.check_auth", side_effect=_authorize_via_linking_key_only) as mock_check_auth:
        rv = client.post(
            f"/api/v1/payment-requests/{invoice.id}/receipts",
            data=json.dumps(filing_data),
            headers=headers,
        )

    assert rv.status_code == 403

    mock_check_auth.assert_called_once()
    called_args, called_kwargs = mock_check_auth.call_args
    assert called_args[0] is None  # business_identifier
    assert called_kwargs.get("account_id") == "OWNER_999"
    assert called_kwargs.get("one_of_roles") == ALL_ALLOWED_ROLES
