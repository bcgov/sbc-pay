# Copyright © 2025 Province of British Columbia
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

"""Tests to assure the refund approval flow.

Test-Suite to ensure that the refund approval flow is working as expected.
"""
import json
from datetime import datetime, timezone

import pytest

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, RefundStatus, RefundType, Role
from pay_api.utils.errors import Error
from tests.utilities.base_test import (
    factory_corp_type_model,
    factory_distribution_code,
    factory_distribution_link,
    factory_fee_model,
    factory_fee_schedule_model,
    factory_filing_type_model,
    factory_payment_account,
    get_claims,
    get_payment_request,
    token_header,
)


def setup_filing_and_account_data(product_code: str, payment_method: str):
    """Set up supporting filing and account data for refund approval flow."""
    test_code = "REFUNDTEST"
    distribution_code = factory_distribution_code(
        name="Test Distribution Code",
        client="100",
        reps_centre="22222",
        service_line="33333",
        stob="4444",
        project_code="5555555",
    )
    distribution_code.save()

    fee_code_model = factory_fee_model(fee_code=test_code, amount=50.00)
    corp_type = factory_corp_type_model(
        corp_type_code=test_code,
        corp_type_description=f"{test_code} description",
        product_code=product_code.upper(),
        refund_approval=True,
    )
    filing_type = factory_filing_type_model(filing_type_code=test_code, filing_description=f"{test_code} filing")

    fee_schedule_with_gst = factory_fee_schedule_model(
        filing_type=filing_type,
        corp_type=corp_type,
        fee_code=fee_code_model,
    )

    factory_distribution_link(
        distribution_code_id=distribution_code.distribution_code_id,
        fee_schedule_id=fee_schedule_with_gst.fee_schedule_id,
    ).save()

    pay_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value, auth_account_id="1234").save()
    cfs_account = CfsAccountModel.find_by_account_id(pay_account.id)[0]
    cfs_account.cfs_party = "1111"
    cfs_account.cfs_account = "1111"
    cfs_account.cfs_site = "1111"
    cfs_account.status = CfsAccountStatus.ACTIVE.value
    cfs_account.payment_method = payment_method
    cfs_account.account_id = pay_account.id
    cfs_account.save()
    return cfs_account


def setup_paid_invoice_data(app, jwt, client, cfs_account, payment_method):
    """Set up supporting invoice data for refund approval flow."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    user_headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    test_code = "REFUNDTEST"
    payment_request = get_payment_request(corp_type=test_code, second_filing_type=test_code)
    payment_request["paymentInfo"] = {"methodOfPayment": payment_method}
    payment_request["filingInfo"]["filingTypes"] = [{"filingTypeCode": test_code}]
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(payment_request),
        headers=user_headers,
    )
    assert rv.status_code == 201
    inv_id = rv.json.get("id")
    inv_payment_method = rv.json.get("paymentMethod")
    assert inv_payment_method == payment_method

    if payment_method in [PaymentMethod.CC.value, PaymentMethod.DIRECT_PAY.value]:
        data = {
            "clientSystemUrl": "http://localhost:8080/transactions/transaction_id=abcd",
            "payReturnUrl": "http://localhost:8080/pay-web",
        }
        receipt_number = "123451"
        rv = client.post(
            f"/api/v1/payment-requests/{inv_id}/transactions",
            data=json.dumps(data),
            headers=user_headers,
        )
        assert rv.status_code == 201
        txn_id = rv.json.get("id")
        rv = client.patch(
            f"/api/v1/payment-requests/{inv_id}/transactions/{txn_id}",
            data=json.dumps({"receipt_number": receipt_number}),
            headers=user_headers,
        )
        assert rv.status_code == 200
    else:
        invoice_model = InvoiceModel.find_by_id(inv_id)
        invoice_model.invoice_status_code = InvoiceStatus.PAID.value
        invoice_model.payment_date = datetime.now(tz=timezone.utc)
        invoice_model.paid = invoice_model.total
        invoice_model.cfs_account_id = cfs_account.id
        invoice_model.save()

    return InvoiceModel.find_by_id(inv_id)


def request_refund(client, invoice, requester_headers):
    """Create refund request."""
    rv = client.post(
        f"/api/v1/payment-requests/{invoice.id}/refunds",
        data=json.dumps({"reason": "Test", "notificationEmail": "test@test.com", "staffComment": "staff comment"}),
        headers=requester_headers,
    )
    return rv


def get_refund_token_headers(app, jwt, token_config: dict):
    """Return refund request token headers by refund flow user type."""
    requester_name = token_config["requester_name"]
    requester_roles = token_config["requester_roles"]
    approver_name = token_config["approver_name"]
    approver_roles = token_config["approver_roles"]
    token = jwt.create_jwt(
        get_claims(
            app_request=app,
            username=requester_name,
            roles=requester_roles,
        ),
        token_header,
    )
    requester_headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    token = jwt.create_jwt(
        get_claims(
            app_request=app,
            username=approver_name,
            roles=approver_roles,
        ),
        token_header,
    )
    approver_headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    return requester_headers, approver_headers


@pytest.mark.parametrize(
    "payment_method",
    [
        # (PaymentMethod.CC.value), # TODO Mock fix
        (PaymentMethod.DIRECT_PAY.value),
        (PaymentMethod.DRAWDOWN.value),
        (PaymentMethod.EFT.value),
        (PaymentMethod.ONLINE_BANKING.value),
        (PaymentMethod.PAD.value),
        (PaymentMethod.EJV.value),
    ],
)
def test_full_refund_approval_flow(
    session, client, jwt, app, monkeypatch, account_admin_mock, send_email_mock, payment_method
):
    """Assert full refund approval flow works correctly."""
    cfs_account = setup_filing_and_account_data("TEST_PRODUCT", payment_method)
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, payment_method)
    token_config = {
        "requester_name": "TEST_REQUESTER",
        "requester_roles": [
            Role.PRODUCT_REFUND_REQUESTER.value,
            Role.PRODUCT_REFUND_VIEWER.value,
            Role.VIEW_ALL_TRANSACTIONS.value,
        ],
        "approver_name": "TEST_APPROVER",
        "approver_roles": [
            Role.PRODUCT_REFUND_APPROVER.value,
            Role.PRODUCT_REFUND_VIEWER.value,
            Role.VIEW_ALL_TRANSACTIONS.value,
        ],
    }
    requester_headers, approver_headers = get_refund_token_headers(app, jwt, token_config)

    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 202
    expected_message = (
        f"Invoice ({invoice.id}) for payment method {invoice.payment_method_code} " f"is pending refund approval."
    )
    assert rv.json.get("message") == expected_message

    refund_id = rv.json["refundId"]
    rv = client.get(f"/api/v1/refunds/{refund_id}", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    refund_result = rv.json

    assert refund_result["refundStatus"] == RefundStatus.PENDING_APPROVAL.value
    assert refund_result["refundReason"] == "Test"
    assert refund_result["staffComment"] == "staff comment"
    assert refund_result["notificationEmail"] == "test@test.com"
    assert refund_result["refundType"] == RefundType.INVOICE.value
    assert refund_result["requestedBy"] == token_config["requester_name"]
    assert refund_result["requestedDate"] is not None
    assert refund_result["decisionBy"] is None
    assert refund_result["decisionDate"] is None
    assert refund_result["declineReason"] is None
    assert refund_result["refundAmount"] == 50

    rv = client.get(f"/api/v1/refunds?refundStatus={RefundStatus.PENDING_APPROVAL.value}", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    assert len(rv.json["items"]) == 1
    assert rv.json["statusTotal"] == 1
    search_result = rv.json["items"][0]
    assert_equal_refunds(search_result, refund_result)

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice.id}/refunds/{refund_id}",
        data=json.dumps(
            {
                "status": RefundStatus.APPROVED.value,
            }
        ),
        headers=approver_headers,
    )

    assert rv.status_code == 200
    result = rv.json

    date_format = "%Y-%m-%dT%H:%M:%S.%f"
    assert result["refundId"] is not None
    assert result["refundStatus"] == RefundStatus.APPROVED.value
    assert result["notificationEmail"] == "test@test.com"
    assert result["refundReason"] == "Test"
    assert result["staffComment"] == "staff comment"
    assert result["requestedBy"] == token_config["requester_name"]
    assert result["requestedDate"] is not None
    assert_date_now(result["requestedDate"], date_format)
    assert result["decisionBy"] == token_config["approver_name"]
    assert result["decisionDate"] is not None
    assert_date_now(result["decisionDate"], date_format)
    assert result["refundAmount"] == invoice.total
    assert result["partialRefundLines"] is not None
    assert len(result["partialRefundLines"]) == 0
    assert result["declineReason"] is None

    refund_partials = RefundsPartialModel.get_partial_refunds_by_refund_id(refund_id)
    assert not refund_partials


@pytest.mark.parametrize(
    "payment_method",
    [
        # (PaymentMethod.CC.value),
        (PaymentMethod.DIRECT_PAY.value),
        (PaymentMethod.DRAWDOWN.value),
        (PaymentMethod.EFT.value),
        (PaymentMethod.ONLINE_BANKING.value),
        (PaymentMethod.PAD.value),
        (PaymentMethod.EJV.value),
    ],
)
def test_full_refund_decline_flow(session, client, jwt, app, monkeypatch, payment_method):
    """Assert full refund approval flow works correctly."""
    cfs_account = setup_filing_and_account_data("TEST_PRODUCT", payment_method)
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, payment_method)
    token_config = {
        "requester_name": "TEST_REQUESTER",
        "requester_roles": [
            Role.PRODUCT_REFUND_REQUESTER.value,
            Role.PRODUCT_REFUND_VIEWER.value,
            Role.VIEW_ALL_TRANSACTIONS.value,
        ],
        "approver_name": "TEST_APPROVER",
        "approver_roles": [
            Role.PRODUCT_REFUND_APPROVER.value,
            Role.PRODUCT_REFUND_VIEWER.value,
            Role.VIEW_ALL_TRANSACTIONS.value,
        ],
    }
    requester_headers, approver_headers = get_refund_token_headers(app, jwt, token_config)

    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 202
    expected_message = (
        f"Invoice ({invoice.id}) for payment method {invoice.payment_method_code} " f"is pending refund approval."
    )
    assert rv.json.get("message") == expected_message

    refund_id = rv.json["refundId"]
    rv = client.get(f"/api/v1/refunds/{refund_id}", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    refund_result = rv.json

    assert refund_result["refundStatus"] == RefundStatus.PENDING_APPROVAL.value
    assert refund_result["refundReason"] == "Test"
    assert refund_result["staffComment"] == "staff comment"
    assert refund_result["notificationEmail"] == "test@test.com"
    assert refund_result["refundType"] == RefundType.INVOICE.value
    assert refund_result["requestedBy"] == token_config["requester_name"]
    assert refund_result["requestedDate"] is not None
    assert refund_result["decisionBy"] is None
    assert refund_result["decisionDate"] is None
    assert refund_result["declineReason"] is None
    assert refund_result["refundAmount"] == 50

    rv = client.get(f"/api/v1/refunds?refundStatus={RefundStatus.PENDING_APPROVAL.value}", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    assert len(rv.json["items"]) == 1
    assert rv.json["statusTotal"] == 1
    search_result = rv.json["items"][0]
    assert_equal_refunds(search_result, refund_result)

    decline_payload = {"status": RefundStatus.DECLINED.value}
    rv = client.patch(
        f"/api/v1/payment-requests/{invoice.id}/refunds/{refund_id}",
        data=json.dumps(decline_payload),
        headers=approver_headers,
    )

    assert rv.status_code == 400
    assert rv.json.get("type") == Error.REFUND_REQUEST_DECLINE_REASON_REQUIRED.name

    decline_payload["declineReason"] = "decline reason"
    rv = client.patch(
        f"/api/v1/payment-requests/{invoice.id}/refunds/{refund_id}",
        data=json.dumps(decline_payload),
        headers=approver_headers,
    )
    assert rv.status_code == 200
    result = rv.json

    date_format = "%Y-%m-%dT%H:%M:%S.%f"
    assert result["refundId"] is not None
    assert result["refundStatus"] == RefundStatus.DECLINED.value
    assert result["notificationEmail"] == "test@test.com"
    assert result["refundReason"] == "Test"
    assert result["staffComment"] == "staff comment"
    assert result["requestedBy"] == token_config["requester_name"]
    assert result["requestedDate"] is not None
    assert_date_now(result["requestedDate"], date_format)
    assert result["decisionBy"] == token_config["approver_name"]
    assert result["decisionDate"] is not None
    assert_date_now(result["decisionDate"], date_format)
    assert result["refundAmount"] == invoice.total
    assert result["partialRefundLines"] is not None
    assert len(result["partialRefundLines"]) == 0
    assert result["declineReason"] == decline_payload["declineReason"]

    refund_partials = RefundsPartialModel.get_partial_refunds_by_refund_id(refund_id)
    assert not refund_partials

    # Confirm we can create a new refund request after a previous decline
    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 202
    assert rv.json.get("message") == expected_message


def assert_equal_refunds(search_result: dict, refund_result: dict):
    """Assert two refund response items are equal."""
    assert search_result["refundId"] == refund_result["refundId"]
    assert search_result["refundStatus"] == refund_result["refundStatus"]
    assert search_result["refundReason"] == refund_result["refundReason"]
    assert search_result["staffComment"] == refund_result["staffComment"]
    assert search_result["notificationEmail"] == refund_result["notificationEmail"]
    assert search_result["refundType"] == refund_result["refundType"]
    assert search_result["requestedBy"] == refund_result["requestedBy"]
    assert search_result["requestedDate"] == refund_result["requestedDate"]
    assert search_result["decisionBy"] == refund_result["decisionBy"]
    assert search_result["decisionDate"] == refund_result["decisionDate"]
    assert search_result["declineReason"] == refund_result["declineReason"]
    assert search_result["refundAmount"] == refund_result["refundAmount"]


def assert_date_now(date_string: str, date_format: str):
    """Assert date string against current UTC date."""
    assert datetime.strptime(date_string, date_format).date() == datetime.now(tz=timezone.utc).date()
