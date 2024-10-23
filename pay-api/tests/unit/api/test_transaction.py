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

"""Tests to assure the transactions end-point.

Test-Suite to ensure that the /transactions endpoint is working as expected.
"""

import json
import uuid
from unittest.mock import patch

from requests.exceptions import ConnectionError

from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import PaymentMethod
from tests import skip_in_pod
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    get_claims,
    get_payment_request,
    get_payment_request_with_payment_method,
    token_header,
)


def test_transaction_post(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentId")

    assert schema_utils.validate(rv.json, "transaction")[0]


def test_transaction_post_direct_pay(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_payment_method(payment_method=PaymentMethod.DIRECT_PAY.value)),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentId")
    assert schema_utils.validate(rv.json, "transaction")[0]


def test_transaction_post_with_invalid_return_url(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://google.com/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400


def test_transaction_post_no_redirect_uri(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps({}),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400


def test_transactions_post_invalid_payment(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    invoice_id = 9999
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps({}),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400


def test_transaction_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    txn_id = rv.json.get("id")
    rv = client.get(f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("paymentId")
    assert rv.json.get("id") == txn_id
    assert schema_utils.validate(rv.json, "transaction")[0]


def test_transaction_get_invalid_payment_and_transaction(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )

    invalid_txn_id = uuid.uuid4()
    rv = client.get(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{invalid_txn_id}",
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == "INVALID_TRANSACTION_ID"


def test_transaction_put(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    txn_id = rv.json.get("id")
    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 200


def test_transaction_put_with_no_receipt(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    txn_id = rv.json.get("id")
    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps({}),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 200


@skip_in_pod
def test_transaction_put_completed_payment(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )

    txn_id = rv.json.get("id")
    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps({}),
        headers={"content-type": "application/json"},
    )

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps({}),
        headers={"content-type": "application/json"},
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == "INVALID_TRANSACTION"


def test_transactions_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    transactions_link = "/api/v1/payment-requests/{}/transactions".format(rv.json.get("id"))
    rv = client.get(f"{transactions_link}", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("items") is not None
    assert len(rv.json.get("items")) == 0

    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"{transactions_link}",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    txn_id = rv.json.get("id")
    rv = client.get(f"{transactions_link}/{txn_id}", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("id") == txn_id

    rv = client.get(f"{transactions_link}", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("items") is not None
    assert len(rv.json.get("items")) == 1

    assert schema_utils.validate(rv.json, "transactions")[0]


@skip_in_pod
def test_transaction_patch_completed_payment_and_transaction_status(session, client, jwt, app):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )

    txn_id = rv.json.get("id")
    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps({}),
        headers={"content-type": "application/json"},
    )

    assert rv.status_code == 200
    assert rv.json.get("statusCode") == "COMPLETED"


@skip_in_pod
def test_transaction_patch_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    txn_id = rv.json.get("id")
    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectionError("mocked error"),
    ):
        rv = client.patch(
            f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
            data=json.dumps({"receipt_number": receipt_number}),
            headers={"content-type": "application/json"},
        )
        assert rv.status_code == 200
        assert rv.json.get("paySystemReasonCode") == "SERVICE_UNAVAILABLE"


@skip_in_pod
def test_transaction_patch_direct_pay(session, client, jwt, app):
    """Assert that the transaction patch updates the payment receipts."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create a payment first
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_payment_method(payment_method=PaymentMethod.DIRECT_PAY.value)),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payment-requests/{invoice_id}/transactions",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    txn_id = rv.json.get("id")
    assert rv.status_code == 201
    assert rv.json.get("paymentId")

    url = (
        "trnApproved=0&messageText=Duplicate%20Order%20Number%20-%20This%20order%20number%20has%20already%20been"
        "%20processed&trnOrderId=169124&trnAmount=31.50&paymentMethod=CC&cardType=MC&authCode=null&trnDate=2020-12"
        "-17&pbcTxnNumber=REG00001593&hashValue=a5a48bf399af4e18c2233078ebabff73"
    )
    param = {"payResponseUrl": url}

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}/transactions/{txn_id}",
        data=json.dumps(param),
        headers={"content-type": "application/json"},
    )
    assert rv.json.get("paySystemReasonCode") == "DUPLICATE_ORDER_NUMBER"
    # Get payment details


def test_transaction_post_for_nsf_payment(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    # Create payment for NSF payment.
    payment_2 = factory_payment(
        payment_status_code="CREATED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.CC.value,
    )
    payment_2.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    rv = client.post(
        f"/api/v1/payments/{payment_2.id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )

    assert rv.status_code == 201
    assert rv.json.get("paymentId") == payment_2.id

    assert schema_utils.validate(rv.json, "transaction")[0]


def test_valid_redirect_url(session, jwt, client, app):
    """Assert the valid redirect url endpoint works."""
    old_urls = app.config["VALID_REDIRECT_URLS"]
    data = {"redirectUrl": "https://www.google.ca"}
    headers = {"content-type": "application/json"}
    rv = client.post(
        "/api/v1/valid-redirect-url",
        data=json.dumps(data),
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("isValid") is False
    app.config["VALID_REDIRECT_URLS"] = ["https://www.google.ca"]
    rv = client.post(
        "/api/v1/valid-redirect-url",
        data=json.dumps(data),
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("isValid") is True
    app.config["VALID_REDIRECT_URLS"] = old_urls
