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
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Refund as RefundModel
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import (
    CfsAccountStatus,
    InvoiceStatus,
    PaymentMethod,
    RefundsPartialType,
    RefundStatus,
    RefundType,
    Role,
    RolePattern,
)
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


def setup_filing_and_account_data(
    product_code: str, payment_method: str, refund_approval: bool = True
) -> CfsAccountModel:
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
        refund_approval=refund_approval,
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

    if payment_method == PaymentMethod.DIRECT_PAY.value:
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
        invoice_model.payment_date = datetime.now(tz=UTC)
        invoice_model.paid = invoice_model.total
        invoice_model.cfs_account_id = cfs_account.id
        invoice_model.save()

    return InvoiceModel.find_by_id(inv_id)


def request_refund(
    client, invoice, request_headers, refund_revenue: list[dict] = None, use_original_user_header: bool = False
):
    """Create refund request."""
    payload = {"reason": "Test", "notificationEmail": "test@test.com", "staffComment": "staff comment"}
    if refund_revenue:
        payload["refundRevenue"] = refund_revenue

    if use_original_user_header:
        request_headers["original_user"] = "ORIGINAL_USER"

    rv = client.post(
        f"/api/v1/payment-requests/{invoice.id}/refunds",
        data=json.dumps(payload),
        headers=request_headers,
    )
    return rv


def get_refund_token_headers(app, jwt, token_config: dict):
    """Return refund request token headers by refund flow user type."""
    requester_headers = None
    approver_headers = None

    if token_config.get("requester_name") and token_config.get("requester_roles"):
        token = jwt.create_jwt(
            get_claims(
                app_request=app,
                username=token_config["requester_name"],
                roles=token_config["requester_roles"],
            ),
            token_header,
        )
        requester_headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    if token_config.get("approver_name") and token_config.get("approver_roles"):
        token = jwt.create_jwt(
            get_claims(
                app_request=app,
                username=token_config["approver_name"],
                roles=token_config["approver_roles"],
            ),
            token_header,
        )
        approver_headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    return requester_headers, approver_headers


@pytest.mark.parametrize(
    "refund_status",
    [
        (RefundStatus.PENDING_APPROVAL.value),
        (RefundStatus.APPROVED.value),
        (RefundStatus.APPROVAL_NOT_REQUIRED.value),
    ],
)
def test_refund_state_validation(
    session, client, jwt, app, monkeypatch, refund_service_mocks, account_admin_mock, send_email_mock, refund_status
):
    """Assert refund state validation works correctly."""
    cfs_account = setup_filing_and_account_data("TEST_PRODUCT", PaymentMethod.DIRECT_PAY.value)
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, PaymentMethod.DIRECT_PAY.value)
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
    refund_id = rv.json["refundId"]

    refund = RefundModel.find_by_id(refund_id)
    if refund.status != refund_status:
        refund.status = refund.status
        refund.save()

    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 400
    assert rv.json.get("type") == Error.INVALID_REQUEST.name


@pytest.mark.parametrize(
    "payment_method",
    [
        (PaymentMethod.DIRECT_PAY.value),
        (PaymentMethod.DRAWDOWN.value),
        (PaymentMethod.EFT.value),
        (PaymentMethod.ONLINE_BANKING.value),
        (PaymentMethod.PAD.value),
        (PaymentMethod.EJV.value),
    ],
)
def test_full_refund_approval_flow(
    session, client, jwt, app, monkeypatch, refund_service_mocks, account_admin_mock, send_email_mock, payment_method
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
    refund_service_mocks["get_auth_user"].assert_called_once()
    refund_service_mocks["get_auth_user"].reset_mock()
    refund_service_mocks["send_email_async"].assert_called_once()
    refund_service_mocks["send_email_async"].reset_mock()

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

    assert refund_service_mocks["send_email_async"].call_count == 2
    refund_service_mocks["send_email_async"].reset_mock()

    rv = client.get(f"/api/v1/payment-requests/{invoice.id}/composite", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    assert rv.json["id"] == invoice.id
    assert rv.json["partialRefunds"] is None


@pytest.mark.parametrize(
    "payment_method",
    [
        (PaymentMethod.DIRECT_PAY.value),
        (PaymentMethod.DRAWDOWN.value),
        (PaymentMethod.EFT.value),
        (PaymentMethod.ONLINE_BANKING.value),
        (PaymentMethod.PAD.value),
        (PaymentMethod.EJV.value),
    ],
)
def test_full_refund_decline_flow(session, client, jwt, app, monkeypatch, refund_service_mocks, payment_method):
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
    refund_service_mocks["send_email_async"].assert_called_once()
    refund_service_mocks["send_email_async"].reset_mock()

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

    refund_service_mocks["send_email_async"].assert_called_once()
    refund_service_mocks["send_email_async"].reset_mock()

    rv = client.get(f"/api/v1/payment-requests/{invoice.id}/composite", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    assert rv.json["id"] == invoice.id
    assert rv.json["partialRefunds"] is None

    # Confirm we can create a new refund request after a previous decline
    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 202
    assert rv.json.get("message") == expected_message


@pytest.mark.parametrize(
    "payment_method",
    [
        (PaymentMethod.DIRECT_PAY.value),
    ],
)
def test_partial_refund_approval_flow(
    session, client, jwt, app, monkeypatch, refund_service_mocks, account_admin_mock, send_email_mock, payment_method
):
    """Assert partial refund approval flow works correctly."""
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
    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
    refund_amount = float(payment_line_items[0].filing_fees / 2)

    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": refund_amount,
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    rv = request_refund(client, invoice, requester_headers, refund_revenue)
    assert rv.status_code == 202
    expected_message = (
        f"Invoice ({invoice.id}) for payment method {invoice.payment_method_code} " f"is pending refund approval."
    )
    assert rv.json.get("message") == expected_message
    refund_service_mocks["send_email_async"].assert_called_once()
    refund_service_mocks["send_email_async"].reset_mock()

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
    assert refund_result["refundAmount"] == refund_amount
    assert refund_result["partialRefundLines"]
    assert len(refund_result["partialRefundLines"]) == 1
    refund_line = refund_result["partialRefundLines"][0]
    assert refund_line["paymentLineItemId"] == invoice.payment_line_items[0].id
    assert refund_line["description"] == invoice.payment_line_items[0].description
    assert refund_line["futureEffectiveFeeAmount"] == 0
    assert refund_line["priorityFeeAmount"] == 0
    assert refund_line["serviceFeeAmount"] == 0
    assert refund_line["statutoryFeeAmount"] == refund_amount

    rv = client.get(f"/api/v1/refunds?refundStatus={RefundStatus.PENDING_APPROVAL.value}", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    assert len(rv.json["items"]) == 1
    assert rv.json["statusTotal"] == 1
    search_result = rv.json["items"][0]
    assert len(search_result["partialRefundLines"]) == 1
    assert_equal_refunds(search_result, refund_result)

    rv = client.get(f"/api/v1/payment-requests/{invoice.id}/composite", headers=requester_headers)
    assert rv.status_code == 200
    assert rv.json
    assert rv.json["id"] == invoice.id
    assert rv.json["partialRefunds"]
    assert len(rv.json["partialRefunds"]) == 1

    with patch("pay_api.services.direct_pay_service.DirectPayService.get") as mock_get:
        mock_get.return_value.ok = True
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "pbcrefnumber": "10007",
            "trnnumber": "1",
            "trndate": "2023-03-06",
            "description": "Direct_Sale",
            "trnamount": "31.5",
            "paymentmethod": "CC",
            "currency": "CAD",
            "gldate": "2023-03-06",
            "paymentstatus": "CMPLT",
            "trnorderid": "23525252",
            "paymentauthcode": "TEST",
            "cardtype": "VI",
            "revenue": [
                {
                    "linenumber": "1",
                    "revenueaccount": "100.22222.33333.4444.5555555.000000.0000",
                    "revenueamount": "30",
                    "glstatus": "CMPLT",
                    "glerrormessage": None,
                    "refund_data": [
                        {
                            "txn_refund_distribution_id": 103570,
                            "revenue_amount": 25,
                            "refund_date": "2023-04-15T20:13:36Z",
                            "refundglstatus": "CMPLT",
                            "refundglerrormessage": None,
                        }
                    ],
                },
            ],
            "postedrefundamount": None,
            "refundedamount": None,
        }
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
        assert result["refundAmount"] == refund_amount
        assert result["partialRefundLines"] is not None
        assert len(result["partialRefundLines"]) == 1
        assert result["declineReason"] is None

        assert refund_service_mocks["send_email_async"].call_count == 2
        refund_service_mocks["send_email_async"].reset_mock()

        rv = client.get(f"/api/v1/payment-requests/{invoice.id}/composite", headers=requester_headers)
        assert rv.status_code == 200
        assert rv.json
        assert rv.json["id"] == invoice.id
        assert rv.json["partialRefunds"]
        assert len(rv.json["partialRefunds"]) == 1


def test_cc_refund_should_reject(
    session, client, jwt, app, monkeypatch, refund_service_mocks, account_admin_mock, send_email_mock
):
    """Assert full refund approval flow works correctly."""
    cfs_account = setup_filing_and_account_data("TEST_PRODUCT", PaymentMethod.CC.value)
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, PaymentMethod.CC.value)
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
    assert rv.status_code == 400
    assert rv.json["type"] == Error.FULL_REFUND_INVOICE_INVALID_STATE.name


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
    assert datetime.strptime(date_string, date_format).date() == datetime.now(tz=UTC).date()


def test_invoice_composite_full_refund(
    session, client, jwt, app, monkeypatch, refund_service_mocks, account_admin_mock, send_email_mock
):
    """Assert full refund approval flow works correctly."""
    payment_method = PaymentMethod.DIRECT_PAY.value
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
    rv = client.get(
        f"/api/v1/payment-requests/{invoice.id}/composite",
        headers=requester_headers,
    )

    assert rv.status_code == 200
    assert rv.json
    invoice_composite = rv.json
    assert invoice_composite["id"] == invoice.id
    assert invoice_composite["latestRefundId"] is None
    assert invoice_composite["latestRefundStatus"] is None
    assert invoice_composite["partialRefundable"] is True
    assert invoice_composite["partialRefunds"] is None
    assert invoice_composite["fullRefundable"] is True

    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 202
    refund = rv.json

    rv = client.get(
        f"/api/v1/payment-requests/{invoice.id}/composite",
        headers=requester_headers,
    )
    assert rv.status_code == 200
    assert rv.json
    invoice_composite = rv.json

    assert invoice_composite["id"] == invoice.id
    assert invoice_composite["latestRefundId"] == refund["refundId"]
    assert invoice_composite["latestRefundStatus"] == RefundStatus.PENDING_APPROVAL.value
    assert invoice_composite["partialRefundable"] is True
    assert invoice_composite["partialRefunds"] is None
    assert invoice_composite["fullRefundable"] is True


@pytest.mark.parametrize(
    "role",
    [
        ("bca" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("btr" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("business" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("business_search" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("cso" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("esra" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("mhr" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("ppr" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("rppr" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("rpt" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("sofi" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("strr" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("vs" + RolePattern.PRODUCT_REFUND_REQUESTER.value),
        ("test_product" + RolePattern.PRODUCT_REFUND_APPROVER.value),
        Role.PRODUCT_REFUND_APPROVER.value,
    ],
)
def test_refund_requester_unauthorized(session, client, jwt, app, monkeypatch, refund_service_mocks, role):
    """Assert allowed products still properly checked when refund approval is not True."""
    cfs_account = setup_filing_and_account_data(
        product_code="TEST_PRODUCT", payment_method=PaymentMethod.DIRECT_PAY.value, refund_approval=False
    )
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, PaymentMethod.DIRECT_PAY.value)
    token_config = {"requester_name": "TEST_REQUESTER", "requester_roles": [Role.PRODUCT_REFUND_VIEWER.value, role]}
    requester_headers, approver_headers = get_refund_token_headers(app, jwt, token_config)
    rv = request_refund(client, invoice, requester_headers)
    assert rv.status_code == 403
    if rv.json.get("type"):
        assert rv.json.get("type") == Error.REFUND_INSUFFICIENT_PRODUCT_AUTHORIZATION.name


@pytest.mark.parametrize(
    "role,refund_approval,expect_pending_approval,use_original_user_header",
    [
        (Role.SYSTEM.value, True, False, False),
        (Role.SYSTEM.value, True, False, True),
        (Role.SYSTEM.value, False, False, False),
        (Role.FAS_REFUND.value, True, True, False),
        (Role.FAS_REFUND.value, True, True, True),
        (Role.FAS_REFUND.value, False, False, False),
        (Role.CREATE_CREDITS.value, True, True, False),
        (Role.CREATE_CREDITS.value, True, True, True),
        (Role.CREATE_CREDITS.value, False, False, False),
    ],
)
def test_regression_roles_create_refund_request(
    session,
    client,
    jwt,
    app,
    monkeypatch,
    refund_service_mocks,
    send_email_mock,
    role,
    refund_approval,
    expect_pending_approval,
    use_original_user_header,
):
    """Assert backwards compatibility for existing roles on refund creation."""
    cfs_account = setup_filing_and_account_data(
        product_code="TEST_PRODUCT", payment_method=PaymentMethod.DIRECT_PAY.value, refund_approval=refund_approval
    )
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, PaymentMethod.DIRECT_PAY.value)
    token_config = {"requester_name": "requester", "requester_roles": [role]}
    system_headers, _ = get_refund_token_headers(app, jwt, token_config)
    rv = request_refund(client, invoice, system_headers)

    assert rv.status_code == 202
    refund = RefundModel.find_by_id(rv.json["refundId"])
    assert refund
    if expect_pending_approval:
        assert refund.status == RefundStatus.PENDING_APPROVAL.value
        assert (
            rv.json.get("message")
            == f"Invoice ({invoice.id}) for payment method {invoice.payment_method_code} is pending refund approval."
        )
        refund_service_mocks["send_email_async"].assert_called_once()
        if role == Role.SYSTEM.value and not use_original_user_header:
            refund_service_mocks["get_auth_user"].assert_not_called()
        else:
            refund_service_mocks["get_auth_user"].assert_called_once()
    else:
        assert refund.status == RefundStatus.APPROVAL_NOT_REQUIRED.value
        assert rv.json.get("message") == REFUND_SUCCESS_MESSAGES[f"{PaymentMethod.DIRECT_PAY.value}.PAID"]
        refund_service_mocks["send_email_async"].assert_not_called()
        refund_service_mocks["get_auth_user"].assert_not_called()


@pytest.mark.parametrize(
    "role,refund_approval",
    [
        (Role.SYSTEM.value, True),
        (Role.SYSTEM.value, False),
        (Role.FAS_REFUND.value, True),
        (Role.FAS_REFUND.value, False),
        (Role.CREATE_CREDITS.value, True),
        (Role.CREATE_CREDITS.value, False),
    ],
)
def test_regression_roles_approval_decline_unauthorized(
    session, client, jwt, app, monkeypatch, refund_service_mocks, send_email_mock, role, refund_approval
):
    """Assert allowed products check allows refund creation when refund approval is not True."""
    cfs_account = setup_filing_and_account_data(
        product_code="TEST_PRODUCT", payment_method=PaymentMethod.DIRECT_PAY.value, refund_approval=refund_approval
    )
    invoice = setup_paid_invoice_data(app, jwt, client, cfs_account, PaymentMethod.DIRECT_PAY.value)
    token_config = {"requester_name": "requester", "requester_roles": [role]}
    system_headers, _ = get_refund_token_headers(app, jwt, token_config)
    rv = request_refund(client, invoice, system_headers)
    assert rv.status_code == 202

    refund_id = rv.json["refundId"]
    refund = RefundModel.find_by_id(refund_id)
    assert refund
    refund.status = RefundStatus.PENDING_APPROVAL.value
    refund.save()

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice.id}/refunds/{refund_id}",
        data=json.dumps({"status": RefundStatus.DECLINED.value, "declineReason": "Test reason"}),
        headers=system_headers,
    )

    assert rv.status_code == 403
