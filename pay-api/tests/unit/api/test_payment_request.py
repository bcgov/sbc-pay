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

"""Tests to assure the payments end-point.

Test-Suite to ensure that the /payment-requests endpoint is working as expected.
"""

import copy
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import current_app
from requests.exceptions import ConnectionError

from pay_api.models import CorpType, FeeCode, FilingType
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import DistributionCodeLink as DistributionCodeLinkModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models.tax_rate import TaxRate
from pay_api.schemas import utils as schema_utils
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, Role, RoutingSlipStatus, TransactionStatus
from tests.utilities.base_test import (
    activate_pad_account,
    get_basic_account_payload,
    get_claims,
    get_gov_account_payload,
    get_payment_request,
    get_payment_request_for_wills,
    get_payment_request_with_folio_number,
    get_payment_request_with_no_contact_info,
    get_payment_request_with_payment_method,
    get_payment_request_with_service_fees,
    get_payment_request_without_bn,
    get_premium_account_payload,
    get_routing_slip_request,
    get_unlinked_pad_account_payload,
    get_waive_fees_payment_request,
    get_zero_dollar_payment_request,
    token_header,
)


def test_payment_request_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    req_data = copy.deepcopy(get_payment_request())
    details = [{"label": "TEST", "value": "TEST"}]
    req_data["details"] = details

    rv = client.post("/api/v1/payment-requests", data=json.dumps(req_data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert schema_utils.validate(rv.json, "invoice")[0]
    assert details[0] in rv.json.get("details")


def test_payment_creation_using_direct_pay(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0001239")),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None

    assert schema_utils.validate(rv.json, "invoice")[0]
    assert rv.json.get("paymentMethod") == "DIRECT_PAY"
    assert rv.json.get("isPaymentActionRequired")


@pytest.mark.parametrize(
    "payload, product_code_claim, expected_status",
    [
        (
            get_payment_request_with_service_fees(corp_type="BEN"),
            "BUSINESS",
            201,
        ),  # Business SA creating business invoice
        (
            get_payment_request_with_service_fees(corp_type="BEN"),
            "CSO",
            403,
        ),  # Business SA creating CSO invoice
        (
            get_payment_request_with_service_fees(corp_type="CSO", filing_type="CSCRMTFC"),
            "CSO",
            201,
        ),  # CSO SA and CSA inv
    ],
)
def test_payment_creation_with_service_account(session, client, jwt, app, payload, product_code_claim, expected_status):
    """Assert that the endpoint returns 201."""
    # Point CSO fee schedule to a valid distribution code.
    fee_schedule_id = FeeScheduleModel.find_by_filing_type_and_corp_type("CSO", "CSCRMTFC").fee_schedule_id
    DistributionCodeLinkModel(fee_schedule_id=fee_schedule_id, distribution_code_id=1).save()

    token = jwt.create_jwt(
        get_claims(
            roles=[Role.SYSTEM.value, Role.EDITOR.value],
            product_code=product_code_claim,
        ),
        token_header,
    )
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == expected_status


def test_payment_creation_for_unauthorized_user(session, client, jwt, app):
    """Assert that the endpoint returns 403."""
    token = jwt.create_jwt(get_claims(username="TEST", login_source="PASSCODE"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0000000")),
        headers=headers,
    )
    assert rv.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {  # Incomplete input
            "paymentInfo": {"methodOfPayment": "CC"},
            "businessInfo": {
                "businessIdentifier": "CP0001234",
                "corpType": "CP",
                "businessName": "ABC Corp",
                "contactInfo": {
                    "city": "Victoria",
                    "postalCode": "V8P2P2",
                    "province": "BC",
                    "addressLine1": "100 Douglas Street",
                    "country": "CA",
                },
            },
        },
        {
            "businessInfo": {
                "businessIdentifier": "CP0001234",
                "corpType": "PC",  # Invalid corp type
                "businessName": "ABC Corp",
                "contactInfo": {
                    "city": "Victoria",
                    "postalCode": "V8P2P2",
                    "province": "BC",
                    "addressLine1": "100 Douglas Street",
                    "country": "CA",
                },
            },
            "filingInfo": {
                "filingTypes": [
                    {"filingTypeCode": "OTADD", "filingDescription": "TEST"},
                    {"filingTypeCode": "OTANN"},
                ]
            },
        },
        {
            "businessInfo": {
                "businessIdentifier": "CP0001234",
                "corpType": "CP",
                "businessName": "ABC Corp",
                "contactInfo": {
                    "city": "Victoria",
                    "postalCode": "V8P2P2",
                    "province": "BC",
                    "addressLine1": "100 Douglas Street",
                    "country": "CA",
                },
            },
            "filingInfo": {
                "filingTypes": [
                    # No filing types
                ]
            },
        },
    ],
)
def test_payment_invalid_request(session, client, jwt, app, payload):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, "problem")[0]


def test_payment_get(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inv_id = rv.json.get("id")
    rv = client.get(f"/api/v1/payment-requests/{inv_id}", headers=headers)
    assert rv.status_code == 200
    assert schema_utils.validate(rv.json, "invoice")[0]


def test_payment_get_exception(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    pay_id = "123456sdf"

    rv = client.get(f"/api/v1/payment-requests/{pay_id}", headers=headers)
    assert rv.status_code == 404

    pay_id = "99999999999999"

    rv = client.get(f"/api/v1/payment-requests/{pay_id}", headers=headers)
    assert rv.status_code == 500


def test_payment_creation_when_paybc_down(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": "1234",
    }

    # Create an account first with CC as preffered payment, and it will create a DIRECT_PAY account

    account_payload = get_basic_account_payload(PaymentMethod.CC.value)
    client.post("/api/v1/accounts", data=json.dumps(account_payload), headers=headers)

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("isPaymentActionRequired")
    invoice_id = rv.json.get("id")

    # Try a search with business identifier and assert result
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    business_identifier = get_payment_request()["businessInfo"]["businessIdentifier"]
    rv = client.get(
        f"/api/v1/payment-requests?businessIdentifier={business_identifier}",
        headers=headers,
    )
    assert rv.status_code == 200
    assert len(rv.json["invoices"]) == 1
    assert rv.json["invoices"][0]["businessIdentifier"] == business_identifier
    assert rv.json["invoices"][0]["id"] == invoice_id
    assert rv.json["invoices"][0]["paymentAccount"]["accountId"] == str(account_payload["accountId"])


def test_zero_dollar_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role="staff"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_zero_dollar_payment_request()),
        headers=headers,
    )

    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("statusCode", None) == "COMPLETED"

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_zero_dollar_payment_creation_for_unaffiliated_entity(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role="staff"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_zero_dollar_payment_request(business_identifier="CP0001237")),
        headers=headers,
    )

    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("statusCode", None) == "COMPLETED"

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_delete_payment(session, client, jwt, app):
    """Assert that the endpoint returns 204."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    pay_id = rv.json.get("id")
    rv = client.delete(f"/api/v1/payment-requests/{pay_id}", headers=headers)
    assert rv.status_code == 202


def test_delete_completed_payment(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(role="staff"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_zero_dollar_payment_request()),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("statusCode", None) == "COMPLETED"

    pay_id = rv.json.get("id")
    rv = client.delete(f"/api/v1/payment-requests/{pay_id}", headers=headers)
    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, "problem")[0]


def test_payment_delete_when_paybc_is_down(session, client, jwt, app):
    """Assert that the endpoint returns 202. The payment will be acceoted to delete."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    pay_id = rv.json.get("id")

    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectionError("mocked error"),
    ):
        rv = client.delete(f"/api/v1/payment-requests/{pay_id}", headers=headers)
        assert rv.status_code == 202


def test_payment_creation_with_routing_slip(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    data = get_payment_request()
    data["accountInfo"] = {"routingSlip": "TEST_ROUTE_SLIP"}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("routingSlip") == "TEST_ROUTE_SLIP"

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_zero_dollar_payment_creation_with_existing_routing_slip(session, client, jwt):
    """Assert that the endpoint returns 201."""
    claims = get_claims(
        roles=[
            Role.FAS_CREATE.value,
            Role.FAS_SEARCH.value,
            Role.STAFF.value,
            "make_payment",
        ]
    )
    token = jwt.create_jwt(claims, token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    payload = get_routing_slip_request()
    rv = client.post("/api/v1/fas/routing-slips", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    rs_number = rv.json.get("number")

    data = get_zero_dollar_payment_request()
    data["accountInfo"] = {"routingSlip": rs_number}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    total = rv.json.get("total")
    rv = client.post(
        "/api/v1/fas/routing-slips/queries",
        data=json.dumps({"routingSlipNumber": rs_number}),
        headers=headers,
    )

    items = rv.json.get("items")

    assert items[0].get("remainingAmount") == payload.get("payments")[0].get("paidAmount") - total


@pytest.mark.parametrize("payment_requests", [get_payment_request(), get_payment_request_without_bn()])
def test_payment_creation_with_existing_routing_slip(session, client, jwt, payment_requests):
    """Assert that the endpoint returns 201."""
    claims = get_claims(
        roles=[
            Role.FAS_CREATE.value,
            Role.FAS_SEARCH.value,
            Role.STAFF.value,
            "make_payment",
        ]
    )
    token = jwt.create_jwt(claims, token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    payload = get_routing_slip_request()
    rv = client.post("/api/v1/fas/routing-slips", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    rs_number = rv.json.get("number")

    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    data = payment_requests
    data["accountInfo"] = {"routingSlip": rs_number}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    total = rv.json.get("total")
    rv = client.post(
        "/api/v1/fas/routing-slips/queries",
        data=json.dumps({"routingSlipNumber": rs_number}),
        headers=headers,
    )

    items = rv.json.get("items")

    assert items[0].get("remainingAmount") == payload.get("payments")[0].get("paidAmount") - total


def test_payment_creation_with_existing_invalid_routing_slip_invalid(session, client, jwt):
    """Assert that the endpoint returns 201."""
    claims = get_claims(
        roles=[
            Role.FAS_CREATE.value,
            Role.FAS_EDIT.value,
            Role.STAFF.value,
            "make_payment",
            Role.FAS_LINK.value,
        ]
    )
    token = jwt.create_jwt(claims, token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # create an RS with less balance
    cheque_amount = 1
    payload = get_routing_slip_request(
        cheque_receipt_numbers=[("111456789", PaymentMethod.CHEQUE.value, cheque_amount)]
    )
    rv = client.post("/api/v1/fas/routing-slips", data=json.dumps(payload), headers=headers)
    rs_number = rv.json.get("number")

    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    data = get_payment_request()
    data["accountInfo"] = {"routingSlip": rs_number}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert "There is not enough balance in this Routing slip" in rv.json.get("detail")
    assert "INSUFFICIENT_BALANCE_IN_ROUTING_SLIP" in rv.json.get("type")
    assert f"${cheque_amount}.00" in rv.json.get("detail")

    # change status of routing slip to inactive

    rs_model = RoutingSlipModel.find_by_number(rs_number)
    rs_model.status = RoutingSlipStatus.COMPLETE.value
    rs_model.commit()

    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert rv.json.get("type") == "RS_NOT_ACTIVE"

    # change status of routing slip to inactive

    rs_model = RoutingSlipModel.find_by_number(rs_number)
    rs_model.status = RoutingSlipStatus.ACTIVE.value
    rs_model.commit()
    parent1 = get_routing_slip_request(number="206380859")

    client.post("/api/v1/fas/routing-slips", data=json.dumps(parent1), headers=headers)
    link_data = {
        "childRoutingSlipNumber": rs_number,
        "parentRoutingSlipNumber": f"{parent1.get('number')}",
    }
    client.post("/api/v1/fas/routing-slips/links", data=json.dumps(link_data), headers=headers)
    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert "LINKED_ROUTING_SLIP" in rv.json.get("type")
    assert "This Routing slip is linked" in rv.json.get("detail")
    assert parent1.get("number") in rv.json.get("detail")

    # Flip the legacy routing slip flag
    data["accountInfo"] = {"routingSlip": "invalid"}
    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 201
    current_app.config["ALLOW_LEGACY_ROUTING_SLIPS"] = False
    data["accountInfo"] = {"routingSlip": "invalid"}
    rv = client.post("/api/v1/payment-requests", data=json.dumps(data), headers=headers)
    assert rv.status_code == 400
    assert rv.json.get("type") == "RS_DOESNT_EXIST"
    current_app.config["ALLOW_LEGACY_ROUTING_SLIPS"] = True  # reset it back not to affect other tests


def test_bcol_payment_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    payload = {
        "businessInfo": {
            "businessIdentifier": "CP0002000",
            "corpType": "CP",
            "businessName": "ABC Corp",
            "contactInfo": {
                "city": "Victoria",
                "postalCode": "V8P2P2",
                "province": "BC",
                "addressLine1": "100 Douglas Street",
                "country": "CA",
            },
        },
        "filingInfo": {
            "filingTypes": [
                {"filingTypeCode": "OTADD", "filingDescription": "TEST"},
                {"filingTypeCode": "OTANN"},
            ],
            "folioNumber": "TEST",
        },
    }

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_zero_dollar_payment_creation_with_waive_fees(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role="staff"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_waive_fees_payment_request()),
        headers=headers,
    )

    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("statusCode", None) == "COMPLETED"
    assert rv.json.get("paymentMethod", None) == "INTERNAL"
    assert rv.json.get("total") == 0
    assert rv.json.get("total") == 0

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_zero_dollar_payment_creation_with_waive_fees_unauthorized(session, client, jwt, app):
    """Assert that the endpoint returns 401."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_waive_fees_payment_request()),
        headers=headers,
    )

    assert rv.status_code == 401
    assert schema_utils.validate(rv.json, "problem")[0]


def test_premium_payment_creation(session, client, jwt, app, premium_user_mock):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert schema_utils.validate(rv.json, "invoice")[0]


def test_premium_payment_creation_with_payment_method(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(business_identifier="CP0002000", payment_method="DRAWDOWN")
        ),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert schema_utils.validate(rv.json, "invoice")[0]
    assert rv.json.get("paymentMethod") == "DRAWDOWN"


def test_premium_payment_creation_with_payment_method_ob(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(business_identifier="CP0002000", payment_method="ONLINE_BANKING")
        ),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentMethod") == "ONLINE_BANKING"
    invoice_id = rv.json.get("id")

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}",
        data=json.dumps({"paymentInfo": {"methodOfPayment": "CC"}}),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json.get("paymentMethod") == "DIRECT_PAY"


def test_premium_payment_creation_with_payment_method_ob_cc(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(business_identifier="CP0002000", payment_method="ONLINE_BANKING")
        ),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentMethod") == "ONLINE_BANKING"
    assert rv.json.get("isOnlineBankingAllowed")
    invoice_id = rv.json.get("id")

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}",
        data=json.dumps({"paymentInfo": {"methodOfPayment": "CC"}}),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json.get("paymentMethod") == "DIRECT_PAY"

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


def test_cc_payment_with_no_contact_info(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": "1234",
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_no_contact_info(payment_method="CC", filing_type_code="OTANN")),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert schema_utils.validate(rv.json, "invoice")[0]
    assert rv.json.get("paymentMethod") == "CC"


def test_premium_payment_with_no_contact_info(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": "1234",
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_no_contact_info(payment_method="DRAWDOWN", corp_type="PPR")),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert schema_utils.validate(rv.json, "invoice")[0]
    assert rv.json.get("paymentMethod") == "DRAWDOWN"


@pytest.mark.parametrize(
    "folio_number, payload",
    [
        (
            "1234567890",
            get_payment_request_with_folio_number(folio_number="1234567890"),
        ),
        (None, get_payment_request()),
    ],
)
def test_payment_creation_with_folio_number(session, client, jwt, app, folio_number, payload):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None

    assert schema_utils.validate(rv.json, "invoice")[0]
    assert rv.json.get("folioNumber") == folio_number


def test_bcol_payment_creation_by_staff(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(
        get_claims(role="staff", username="idir/tester", login_source="IDIR"),
        token_header,
    )
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    dat_number: str = "C1234567890"
    payload = {
        "accountInfo": {"datNumber": dat_number, "bcolAccountNumber": "000000"},
        "businessInfo": {
            "businessIdentifier": "CP0002000",
            "corpType": "CP",
            "businessName": "ABC Corp",
            "contactInfo": {
                "city": "Victoria",
                "postalCode": "V8P2P2",
                "province": "BC",
                "addressLine1": "100 Douglas Street",
                "country": "CA",
            },
        },
        "filingInfo": {
            "filingTypes": [
                {"filingTypeCode": "OTADD", "filingDescription": "TEST"},
                {"filingTypeCode": "OTANN"},
            ],
            "folioNumber": "TEST",
        },
    }

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("datNumber") == dat_number
    assert rv.json.get("paymentMethod") == "DRAWDOWN"

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_payment_creation_with_service_fees(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_service_fees()),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("serviceFees") > 0

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_payment_creation_with_service_fees_for_zero_fees(session, client, jwt, app):
    """Assert that the service fee is zero if it's a free filing."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_service_fees(filing_type="OTFDR")),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert rv.json.get("serviceFees") == 0

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_bcol_payment_creation_by_system(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(
        get_claims(roles=["system"], username="system tester", login_source=None),
        token_header,
    )
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    dat_number: str = "C1234567890"
    payload = {
        "accountInfo": {"datNumber": dat_number, "bcolAccountNumber": "000000"},
        "businessInfo": {
            "businessIdentifier": "CP0002000",
            "corpType": "CP",
            "businessName": "ABC Corp",
            "contactInfo": {
                "city": "Victoria",
                "postalCode": "V8P2P2",
                "province": "BC",
                "addressLine1": "100 Douglas Street",
                "country": "CA",
            },
        },
        "filingInfo": {
            "filingTypes": [
                {"filingTypeCode": "OTADD", "filingDescription": "TEST"},
                {"filingTypeCode": "OTANN"},
            ],
            "folioNumber": "TEST",
        },
    }

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("datNumber") == dat_number
    assert rv.json.get("paymentMethod") == "DRAWDOWN"

    assert not rv.json.get("isPaymentActionRequired")

    assert schema_utils.validate(rv.json, "invoice")[0]


def test_invoice_pdf(session, client, jwt, app):
    """Test invoice pdf generation."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(business_identifier="CP0002000", payment_method="ONLINE_BANKING")
        ),
        headers=headers,
    )
    invoice_id = rv.json.get("id")
    client.post(f"/api/v1/payment-requests/{invoice_id}/reports", headers=headers)
    assert True


def test_premium_payment_creation_with_ob_disabled(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": "1",
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_no_contact_info(
                corp_type="NRO",
                filing_type_code="NM620",
                payment_method="ONLINE_BANKING",
            )
        ),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentMethod") == "ONLINE_BANKING"
    assert not rv.json.get("isOnlineBankingAllowed")


def test_future_effective_premium_payment_creation_with_ob_disabled(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": "1",
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_no_contact_info(
                corp_type="BEN",
                filing_type_code="BCINC",
                payment_method="ONLINE_BANKING",
                future_effective=True,
            )
        ),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("paymentMethod") == "ONLINE_BANKING"
    assert not rv.json.get("isOnlineBankingAllowed")


def test_create_pad_payment_request_when_account_is_pending(session, client, jwt, app):
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
    assert rv.status_code == 400
    assert rv.json.get("type") == "ACCOUNT_IN_PAD_CONFIRMATION_PERIOD"


def test_create_pad_payment_request(session, client, jwt, app):
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
    activate_pad_account(auth_account_id)

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    payload = get_payment_request_with_no_contact_info(
        corp_type="BEN",
        filing_type_code="BCINC",
        payment_method=PaymentMethod.PAD.value,
    )
    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)

    assert rv.json.get("paymentMethod") == PaymentMethod.PAD.value
    assert not rv.json.get("isOnlineBankingAllowed")
    invoice_id = rv.json["id"]

    # Try a search with business identifier and assert result
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    business_identifier = payload["businessInfo"]["businessIdentifier"]
    rv = client.get(
        f"/api/v1/payment-requests?businessIdentifier={business_identifier}",
        headers=headers,
    )
    assert rv.status_code == 200
    assert len(rv.json["invoices"]) == 1
    assert rv.json["invoices"][0]["businessIdentifier"] == business_identifier
    assert rv.json["invoices"][0]["id"] == invoice_id
    assert rv.json["invoices"][0]["paymentAccount"]["accountId"] == "1234"


def test_payment_request_online_banking_with_credit(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")

    # Update the payment account as ACTIVE
    payment_account = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    payment_account.ob_credit = 51
    payment_account.pad_credit = 0
    payment_account.eft_credit = 0
    payment_account.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(business_identifier="CP0002000", payment_method="ONLINE_BANKING")
        ),
        headers=headers,
    )
    invoice_id = rv.json.get("id")

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}?applyCredit=true",
        data=json.dumps({}),
        headers=headers,
    )

    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    assert payment_account.ob_credit == 1
    assert payment_account.pad_credit == 0
    assert payment_account.eft_credit == 0

    # Now set the credit less than the total of invoice.
    payment_account.ob_credit = 49
    payment_account.pad_credit = 0
    payment_account.eft_credit = 0
    payment_account.save()
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(business_identifier="CP0002000", payment_method="ONLINE_BANKING")
        ),
        headers=headers,
    )
    invoice_id = rv.json.get("id")

    rv = client.patch(
        f"/api/v1/payment-requests/{invoice_id}?applyCredit=true",
        data=json.dumps({}),
        headers=headers,
    )
    # Credit won't be applied as the invoice total is 50 and the credit should remain as 0.
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    assert payment_account.ob_credit == 0
    assert payment_account.pad_credit == 0
    assert payment_account.eft_credit == 0


def test_create_ejv_payment_request(session, client, jwt, app):
    """Assert payment request works for EJV accounts."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Create account first
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_gov_account_payload(account_id=1234)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")

    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    dist_code: DistributionCodeModel = DistributionCodeModel.find_by_active_for_account(payment_account.id)

    assert dist_code
    assert dist_code.account_id == payment_account.id

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    assert rv.json.get("paymentMethod") == PaymentMethod.EJV.value
    assert rv.json.get("statusCode") == InvoiceStatus.APPROVED.value


def test_payment_request_creation_for_wills(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
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
    activate_pad_account(auth_account_id)

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
        headers=headers,
    )

    assert rv.json.get("serviceFees") == 1.5
    assert rv.json.get("total") == 28.5  # Wills Noticee : 17, Alias : 5 each for 2, service fee 1.5
    assert sum(line["serviceFees"] for line in rv.json.get("lineItems")) == 1.5


def test_payment_request_creation_with_account_settings(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    system_token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    system_headers = {
        "Authorization": f"Bearer {system_token}",
        "content-type": "application/json",
    }
    # Create account first
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_gov_account_payload(account_id=1234)),
        headers=system_headers,
    )
    auth_account_id = rv.json.get("accountId")

    # Create account fee details.
    staff_token = jwt.create_jwt(get_claims(role=Role.MANAGE_ACCOUNTS.value), token_header)
    staff_headers = {
        "Authorization": f"Bearer {staff_token}",
        "content-type": "application/json",
    }
    client.post(
        f"/api/v1/accounts/{auth_account_id}/fees",
        data=json.dumps(
            {
                "accountFees": [
                    {
                        "applyFilingFees": False,
                        "serviceFeeCode": "TRF02",  # 1.0
                        "product": "VS",  # Wills
                    }
                ]
            }
        ),
        headers=staff_headers,
    )

    user_token = jwt.create_jwt(get_claims(), token_header)
    user_headers = {
        "Authorization": f"Bearer {user_token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
        headers=user_headers,
    )
    assert rv.json.get("serviceFees") == 1.0
    assert rv.json.get("total") == 1.0  # Wills Noticee : 0, Alias : 0 each for 2, service fee 1.0
    assert rv.json.get("lineItems")[0]["serviceFees"] == 1.0
    assert rv.json.get("lineItems")[1]["serviceFees"] == 0

    # Now change the flag and try
    client.put(
        f"/api/v1/accounts/{auth_account_id}/fees/VS",
        data=json.dumps(
            {
                "applyFilingFees": True,
                "serviceFeeCode": "TRF02",  # 1.0
                "product": "VS",  # Wills
            }
        ),
        headers=staff_headers,
    )

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
        headers=user_headers,
    )
    assert rv.json.get("serviceFees") == 1.0
    assert rv.json.get("total") == 28  # Wills Noticee : 17, Alias : 5 each for 2, service fee 1.0
    assert rv.json.get("lineItems")[0]["serviceFees"] == 1.0
    assert rv.json.get("lineItems")[1]["serviceFees"] == 0

    # Now change the serviceFeeCode
    client.put(
        f"/api/v1/accounts/{auth_account_id}/fees/VS",
        data=json.dumps(
            {
                "applyFilingFees": True,
                "serviceFeeCode": "TRF01",  # 1.0
                "product": "VS",  # Wills
            }
        ),
        headers=staff_headers,
    )

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_for_wills(will_alias_quantity=2)),
        headers=user_headers,
    )
    assert rv.json.get("serviceFees") == 1.5
    assert rv.json.get("total") == 28.5  # Wills Notice : 17, Alias : 5 each for 2, service fee 1.0
    assert rv.json.get("lineItems")[0]["serviceFees"] == 1.5
    assert rv.json.get("lineItems")[1]["serviceFees"] == 0


def test_create_ejv_payment_request_non_billable_account(session, client, jwt, app):
    """Assert payment request works for EJV accounts."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Create account first
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_gov_account_payload(account_id=1234, billable=False)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")

    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    dist_code: DistributionCodeModel = DistributionCodeModel.find_by_active_for_account(payment_account.id)

    assert dist_code
    assert dist_code.account_id == payment_account.id

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    assert rv.json.get("paymentMethod") == PaymentMethod.EJV.value
    assert rv.json.get("statusCode") == "COMPLETED"
    assert rv.json.get("total") == rv.json.get("paid")


@pytest.mark.parametrize(
    "account_payload, pay_method",
    [
        (get_unlinked_pad_account_payload(account_id=1234), PaymentMethod.PAD.value),
        (get_premium_account_payload(account_id=1234), PaymentMethod.DRAWDOWN.value),
    ],
)
def test_create_sandbox_payment_requests(session, client, jwt, app, account_payload, pay_method):
    """Assert payment request works for PAD accounts."""
    app.config["ENVIRONMENT_NAME"] = "sandbox"
    token = jwt.create_jwt(
        get_claims(roles=[Role.SYSTEM.value]),
        token_header,
    )
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Create account first
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(account_payload),
        headers=headers,
    )

    auth_account_id = rv.json.get("accountId")

    token = jwt.create_jwt(get_claims(roles=[Role.SANDBOX.value]), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    payload = get_payment_request()
    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)

    app.config["ENVIRONMENT_NAME"] = "local"

    assert rv.json.get("paymentMethod") == pay_method
    assert rv.json.get("statusCode") == "COMPLETED"


def test_payment_request_creation_using_variable_fee(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    req_data = copy.deepcopy(get_payment_request())
    req_data["filingInfo"]["filingTypes"][0]["fee"] = 100  # This shouldn't be in effect as the fee is not variable.

    rv = client.post("/api/v1/payment-requests", data=json.dumps(req_data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("total") == 50

    # Now change the fee to variable and try again.
    fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(
        req_data["businessInfo"]["corpType"],
        req_data["filingInfo"]["filingTypes"][0]["filingTypeCode"],
    )
    fee_schedule.variable = True
    fee_schedule.save()

    req_data["filingInfo"]["filingTypes"][0]["fee"] = 100  # This should be in effect now.

    rv = client.post("/api/v1/payment-requests", data=json.dumps(req_data), headers=headers)
    assert rv.status_code == 201
    assert rv.json.get("total") == 130


def test_business_identifier_too_long(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    payload = {
        "businessInfo": {
            "businessIdentifier": "2CP000200012345678902",  # 21 characters, 20 max.
            "corpType": "CP",
            "businessName": "ABC Corp",
            "contactInfo": {
                "city": "Victoria",
                "postalCode": "V8P2P2",
                "province": "BC",
                "addressLine1": "100 Douglas Street",
                "country": "CA",
            },
        },
        "filingInfo": {
            "filingTypes": [
                {"filingTypeCode": "OTADD", "filingDescription": "TEST"},
                {"filingTypeCode": "OTANN"},
            ],
            "folioNumber": "TEST",
        },
    }

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payload), headers=headers)
    assert rv.status_code == 400


def test_payment_request_gst_and_service_fees_calculation(session, client, jwt, app):
    """Test comprehensive GST and service fees calculation when creating a payment request."""
    filing_type_code = "COMP_TEST"
    corp_type_code = "COMP_CORP"
    fee_code = "COMP_FEE"
    service_fee_code = "COMP_SVC"
    priority_fee_code = "COMP_PRI"
    future_effective_fee_code = "COMP_FUT"

    main_fee = FeeCode(code=fee_code, amount=Decimal("150.00"))
    main_fee.save()

    service_fee = FeeCode(code=service_fee_code, amount=Decimal("25.50"))
    service_fee.save()

    priority_fee = FeeCode(code=priority_fee_code, amount=Decimal("15.75"))
    priority_fee.save()

    future_effective_fee = FeeCode(code=future_effective_fee_code, amount=Decimal("35.25"))
    future_effective_fee.save()

    corp_type = CorpType(code=corp_type_code, description="Comprehensive Test Corp")
    corp_type.save()

    filing_type = FilingType(code=filing_type_code, description="Comprehensive Test Filing")
    filing_type.save()

    fee_schedule_model = FeeScheduleModel(
        filing_type_code=filing_type_code,
        corp_type_code=corp_type_code,
        fee_code=fee_code,
        fee_start_date=datetime.now(tz=UTC).date(),
        service_fee_code=service_fee_code,
        priority_fee_code=priority_fee_code,
        future_effective_fee_code=future_effective_fee_code,
        gst_added=True,
        show_on_pricelist=True,
    )
    fee_schedule_model.save()

    distribution_code = DistributionCodeModel(
        name="Test Distribution Code",
        client="100",
        responsibility_centre="22222",
        service_line="33333",
        stob="4444",
        project_code="5555555",
        start_date=datetime.now(tz=UTC).date(),
        created_by="test",
    )
    distribution_code.save()

    DistributionCodeLinkModel(
        fee_schedule_id=fee_schedule_model.fee_schedule_id, distribution_code_id=distribution_code.distribution_code_id
    ).save()

    payment_request = get_payment_request(corp_type=corp_type_code, second_filing_type=filing_type_code)

    payment_request["filingInfo"]["filingTypes"] = [
        {
            "filingTypeCode": filing_type_code,
            "priority": True,
            "futureEffective": True,
            "filingDescription": "Comprehensive Test Filing",
        }
    ]
    payment_request["details"] = [{"label": "Test Label", "value": "Test Value"}]

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payment_request), headers=headers)

    assert rv.status_code == 201
    assert rv.json.get("_links") is not None
    assert schema_utils.validate(rv.json, "invoice")[0]

    invoice = rv.json

    assert invoice["serviceFees"] == 25.50

    gst_rate = TaxRate.get_gst_effective_rate(datetime.now(tz=UTC))

    expected_main_fee_gst = Decimal(str(round(150.00 * float(gst_rate), 2)))
    expected_service_fee_gst = Decimal(str(round(25.50 * float(gst_rate), 2)))
    expected_priority_fee_gst = Decimal(str(round(15.75 * float(gst_rate), 2)))
    expected_future_effective_fee_gst = Decimal(str(round(35.25 * float(gst_rate), 2)))

    expected_total_gst = (
        expected_main_fee_gst + expected_service_fee_gst + expected_priority_fee_gst + expected_future_effective_fee_gst
    )
    assert invoice["gst"] == float(expected_total_gst)

    expected_total_before_gst = Decimal("150.00") + Decimal("25.50") + Decimal("15.75") + Decimal("35.25")
    expected_total = expected_total_before_gst + expected_total_gst
    assert invoice["total"] == float(expected_total)

    line_items = invoice.get("lineItems", [])
    assert len(line_items) == 1

    line_item = line_items[0]
    assert line_item["filingFees"] == 150.00
    assert line_item["serviceFees"] == 25.50
    assert line_item["priorityFees"] == 15.75
    assert line_item["futureEffectiveFees"] == 35.25
    assert line_item["statutoryFeesGst"] == float(
        expected_main_fee_gst + expected_priority_fee_gst + expected_future_effective_fee_gst
    )
    assert line_item["serviceFeesGst"] == float(expected_service_fee_gst)
    expected_line_item_total = 150.00 + 15.75 + 35.25
    # Line item total doesn't include GST or service fees because they goto another GL.
    assert line_item["total"] == expected_line_item_total
    assert invoice["corpTypeCode"] == corp_type_code


def test_payment_request_skip_payment(session, client, jwt, app):
    """Assert that the invoice status was moved correctly with ALLOW_SKIP_PAYMENT."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    data = get_payment_request_with_service_fees()
    data["skipPayment"] = True
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(data),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("statusCode") == InvoiceStatus.CREATED.value

    app.config["ALLOW_SKIP_PAYMENT"] = True
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(data),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("statusCode") == TransactionStatus.COMPLETED.value
    assert rv.json.get("paid") == rv.json.get("total")

    # Skip payment EFT invoice references are created later.
    data["paymentInfo"] = {"methodOfPayment": PaymentMethod.EFT.value}
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(data),
        headers=headers,
    )
    assert rv.status_code == 201
    assert rv.json.get("statusCode") == TransactionStatus.COMPLETED.value
    assert rv.json.get("paid") == rv.json.get("total")


def test_payment_request_gst_field_behavior(session, client, jwt, app):
    """Test payment-request POST and GET endpoints have proper GST field behavior."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create an invoice with GST by using a fee schedule that has GST enabled
    filing_type_code = "GSTTEST"
    corp_type_code = "GSTTEST"
    fee_code = "GSTTEST"

    fee_code_model = FeeCode(code=fee_code, amount=Decimal("100.00"))
    fee_code_model.save()

    service_fee_code_model = FeeCode(code="GSTSRV", amount=Decimal("10.00"))
    service_fee_code_model.save()

    corp_type = CorpType(code=corp_type_code, description="GST Test Corp", product="BUSINESS")
    corp_type.save()

    filing_type = FilingType(code=filing_type_code, description="GST Test Filing")
    filing_type.save()

    fee_schedule_with_gst = FeeScheduleModel(
        filing_type_code=filing_type_code,
        corp_type_code=corp_type_code,
        fee_code=fee_code,
        fee_start_date=datetime.now(tz=UTC).date(),
        gst_added=True,
        show_on_pricelist=True,
        service_fee=service_fee_code_model,
    )
    fee_schedule_with_gst.save()

    distribution_code = DistributionCodeModel(
        name="GST Test Distribution Code",
        client="100",
        responsibility_centre="22222",
        service_line="33333",
        stob="4444",
        project_code="5555555",
        start_date=datetime.now(tz=UTC).date(),
        created_by="test",
    )
    distribution_code.save()

    DistributionCodeLinkModel(
        fee_schedule_id=fee_schedule_with_gst.fee_schedule_id,
        distribution_code_id=distribution_code.distribution_code_id,
    ).save()

    # Create invoice with GST
    payment_request_with_gst = get_payment_request(corp_type=corp_type_code, second_filing_type=filing_type_code)
    payment_request_with_gst["filingInfo"]["filingTypes"] = [
        {
            "filingTypeCode": filing_type_code,
            "filingDescription": "GST Test Filing",
        }
    ]

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(payment_request_with_gst),
        headers=headers,
    )

    assert rv.status_code == 201
    payment_request_response = rv.json

    assert "id" in payment_request_response
    assert "statusCode" in payment_request_response

    assert "gst" in payment_request_response, "GST field should be present in POST response when invoice has GST"
    assert payment_request_response["gst"] > 0, "GST amount should be greater than 0"

    if "lineItems" in payment_request_response and payment_request_response["lineItems"]:
        line_item = payment_request_response["lineItems"][0]
        assert "gst" in line_item, "Line item GST field should be present in POST response when invoice has GST"
        assert line_item["gst"] > 0, "Line item GST amount should be greater than 0"
        assert "statutoryFeesGst" in line_item, "statutoryFeesGst should be present when invoice has GST"
        assert "serviceFeesGst" in line_item, "serviceFeesGst should be present when invoice has GST"

    invoice_id = payment_request_response["id"]
    rv = client.get(f"/api/v1/payment-requests/{invoice_id}", headers=headers)

    assert rv.status_code == 200
    get_response = rv.json

    assert "id" in get_response
    assert "statusCode" in get_response
    assert get_response["id"] == invoice_id

    # Verify the GET response has GST fields when GST is present
    assert "gst" in get_response, "GST field should be present in GET response when invoice has GST"
    assert get_response["gst"] > 0, "GST amount should be greater than 0"

    if "lineItems" in get_response and get_response["lineItems"]:
        line_item = get_response["lineItems"][0]
        assert "gst" in line_item, "Line item GST field should be present in GET response when invoice has GST"
        assert line_item["gst"] > 0, "Line item GST amount should be greater than 0"
        assert "statutoryFeesGst" in line_item, "statutoryFeesGst should be present when invoice has GST"
        assert "serviceFeesGst" in line_item, "serviceFeesGst should be present when invoice has GST"

    # Create an invoice without GST by using a fee schedule that has GST disabled
    filing_type_code_no_gst = "NOGSTTEST"
    corp_type_code_no_gst = "NOGSTTEST"
    fee_code_no_gst = "NOGSTTEST"

    fee_code_model_no_gst = FeeCode(code=fee_code_no_gst, amount=Decimal("100.00"))
    fee_code_model_no_gst.save()

    service_fee_code_model_no_gst = FeeCode(code="NOGSTSRV", amount=Decimal("10.00"))
    service_fee_code_model_no_gst.save()

    corp_type_no_gst = CorpType(code=corp_type_code_no_gst, description="No GST Test Corp", product="BUSINESS")
    corp_type_no_gst.save()

    filing_type_no_gst = FilingType(code=filing_type_code_no_gst, description="No GST Test Filing")
    filing_type_no_gst.save()

    fee_schedule_without_gst = FeeScheduleModel(
        filing_type_code=filing_type_code_no_gst,
        corp_type_code=corp_type_code_no_gst,
        fee_code=fee_code_no_gst,
        fee_start_date=datetime.now(tz=UTC).date(),
        gst_added=False,
        show_on_pricelist=True,
        service_fee=service_fee_code_model_no_gst,
    )
    fee_schedule_without_gst.save()

    DistributionCodeLinkModel(
        fee_schedule_id=fee_schedule_without_gst.fee_schedule_id,
        distribution_code_id=distribution_code.distribution_code_id,
    ).save()

    # Create invoice without GST
    payment_request_without_gst = get_payment_request(
        corp_type=corp_type_code_no_gst, second_filing_type=filing_type_code_no_gst
    )
    payment_request_without_gst["filingInfo"]["filingTypes"] = [
        {
            "filingTypeCode": filing_type_code_no_gst,
            "filingDescription": "No GST Test Filing",
        }
    ]

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(payment_request_without_gst),
        headers=headers,
    )

    assert rv.status_code == 201
    payment_request_response_no_gst = rv.json

    # Verify the POST response has GST fields hidden when GST is not present
    assert "gst" not in payment_request_response_no_gst, (
        "GST field should be hidden in POST response when invoice has no GST"
    )

    if "lineItems" in payment_request_response_no_gst and payment_request_response_no_gst["lineItems"]:
        line_item = payment_request_response_no_gst["lineItems"][0]
        assert "gst" in line_item, "Line item GST field should always be present"
        assert line_item["gst"] == 0, "Line item GST amount should be 0 when invoice has no GST"
        assert "statutoryFeesGst" not in line_item, "statutoryFeesGst should be hidden when invoice has no GST"
        assert "serviceFeesGst" not in line_item, "serviceFeesGst should be hidden when invoice has no GST"

    # Test GET payment-request endpoint for invoice without GST
    invoice_id_no_gst = payment_request_response_no_gst["id"]
    rv = client.get(f"/api/v1/payment-requests/{invoice_id_no_gst}", headers=headers)

    assert rv.status_code == 200
    get_response_no_gst = rv.json

    assert "id" in get_response_no_gst
    assert "statusCode" in get_response_no_gst
    assert get_response_no_gst["id"] == invoice_id_no_gst

    # Verify the GET response has GST fields hidden when GST is not present
    assert "gst" not in get_response_no_gst, "GST field should be hidden in GET response when invoice has no GST"

    if "lineItems" in get_response_no_gst and get_response_no_gst["lineItems"]:
        line_item = get_response_no_gst["lineItems"][0]
        assert "gst" in line_item, "Line item GST field should always be present"
        assert line_item["gst"] == 0, "Line item GST amount should be 0 when invoice has no GST"
        assert "statutoryFeesGst" not in line_item, "statutoryFeesGst should be hidden when invoice has no GST"
        assert "serviceFeesGst" not in line_item, "serviceFeesGst should be hidden when invoice has no GST"
