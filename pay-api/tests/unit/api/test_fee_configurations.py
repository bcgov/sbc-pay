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

"""Test Fee results per caller type and fee schedule configuration.

Covers both entry points, which enforce differently: GET /fees gates waiveFees at the
resource layer.

Also covers testing of account overrides which are used by GOV accounts.
"""

import json

import pytest

from pay_api.models import AccountFee, PaymentAccount
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.utils.enums import Role
from tests.utilities.base_test import (
    factory_corp_type_model,
    factory_distribution_code,
    factory_distribution_link,
    factory_fee_model,
    factory_fee_schedule_model,
    factory_filing_type_model,
    factory_payment_account,
    get_claims,
    token_header,
)

FILING_FEE_AMOUNT = 100
SERVICE_FEE_AMOUNT = 1.5
NO_FEE_CODE = "TRF04"
BUSINESS_SEARCH = "BUSINESS_SEARCH"

CALLERS = {
    "staff": lambda: get_claims(role=Role.STAFF.value),
    "system": lambda: get_claims(roles=[Role.SYSTEM.value]),
    "system_excluded": lambda: get_claims(roles=[Role.SYSTEM.value, Role.EXCLUDE_SERVICE_FEES.value]),
    "general": lambda: get_claims(),
}


def get_headers(jwt, caller, account_id=None):
    """Build request headers for a caller key from CALLERS."""
    headers = {
        "Authorization": f"Bearer {jwt.create_jwt(CALLERS[caller](), token_header)}",
        "content-type": "application/json",
    }
    if account_id:
        headers["Account-Id"] = account_id
    return headers


def generate_fee_schedule(
    code,
    *,
    filing_amount=FILING_FEE_AMOUNT,
    service_amount=SERVICE_FEE_AMOUNT,
    variable=False,
    priority_amount=None,
    future_amount=None,
    product=None,
    with_distribution=True,
    statutory_fees_gst_added=False,
    service_fees_gst_added=False,
):
    """Create a test fee schedule."""
    corp_type = factory_corp_type_model(f"{code}C", "TEST", product_code=product)
    filing_type = factory_filing_type_model(f"{code}F", "TEST")
    service_fee = factory_fee_model(f"{code}S", service_amount) if service_amount is not None else None
    schedule = factory_fee_schedule_model(
        filing_type,
        corp_type,
        factory_fee_model(f"{code}M", filing_amount),
        service_fee=service_fee,
        variable=variable,
        statutory_fees_gst_added=statutory_fees_gst_added,
        service_fees_gst_added=service_fees_gst_added,
    )
    if priority_amount is not None:
        schedule.priority_fee_code = factory_fee_model(f"{code}P", priority_amount).code
    if future_amount is not None:
        schedule.future_effective_fee_code = factory_fee_model(f"{code}E", future_amount).code
    schedule.save()

    if with_distribution:
        service_dist = factory_distribution_code(f"{code}svc").save()
        dist = factory_distribution_code(f"{code}main", service_fee_dist_id=service_dist.distribution_code_id).save()
        factory_distribution_link(dist.distribution_code_id, schedule.fee_schedule_id).save()

    return corp_type.code, filing_type.code


def generate_payment_account(auth_account_id, *, product, apply_filing_fees=True, service_fee_code=None):
    """Create an account fee override."""
    account = factory_payment_account(auth_account_id=auth_account_id)
    account.save()
    payment_account = PaymentAccount.find_by_auth_account_id(auth_account_id)
    AccountFee(
        account_id=payment_account.id,
        apply_filing_fees=apply_filing_fees,
        service_fee_code=service_fee_code,
        product=product,
        created_by="TEST",
    ).save()
    return payment_account


def generate_invoice_payload(corp_type, filing_type, **filing_type_overrides):
    """Payment request payload for a single filing type."""
    return {
        "businessInfo": {
            "businessIdentifier": "CP0001234",
            "corpType": corp_type,
            "businessName": "ABC Corp",
            "contactInfo": {
                "city": "Victoria",
                "postalCode": "V1V1V1",
                "province": "BC",
                "addressLine1": "100 Test Street",
                "country": "CA",
            },
        },
        "filingInfo": {"filingTypes": [{"filingTypeCode": filing_type, **filing_type_overrides}]},
    }


def call_get_fees(client, headers, corp_type, filing_type, query=""):
    """Call GET on fees route."""
    return client.get(f"/api/v1/fees/{corp_type}/{filing_type}{query}", headers=headers)


def call_post_invoice(client, headers, corp_type, filing_type, **overrides):
    """Call POST for invoice creation."""
    return client.post(
        "/api/v1/payment-requests",
        data=json.dumps(generate_invoice_payload(corp_type, filing_type, **overrides)),
        headers=headers,
    )


CALLER_SERVICE_FEE_MATRIX = [
    ("staff", 0.0, "staff_never_pays_service_fees"),
    ("system", SERVICE_FEE_AMOUNT, "system_pays_service_fees"),
    ("system_excluded", 0.0, "system_with_exclude_role_exempt"),
    ("general", SERVICE_FEE_AMOUNT, "general_user_pays_service_fees"),
]


@pytest.mark.parametrize(
    "caller,expected_service_fees,test_id",
    CALLER_SERVICE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_fees_by_caller_standard_schedule(session, client, jwt, app, caller, expected_service_fees, test_id):
    """Fees route applies the service fee per caller type on a standard schedule."""
    corp_type, filing_type = generate_fee_schedule("STD", with_distribution=False)

    rv = call_get_fees(client, get_headers(jwt, caller), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == FILING_FEE_AMOUNT
    assert rv.json.get("serviceFees") == expected_service_fees


@pytest.mark.parametrize(
    "caller,expected_service_fees,test_id",
    CALLER_SERVICE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_fees_by_caller_zero_filing_fee_with_service_fee(
    session, client, jwt, app, caller, expected_service_fees, test_id
):
    """A zero filing fee should still be able to have a configured service fee."""
    corp_type, filing_type = generate_fee_schedule("ZSF", filing_amount=0, with_distribution=False)

    rv = call_get_fees(client, get_headers(jwt, caller), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == 0
    assert rv.json.get("serviceFees") == expected_service_fees


@pytest.mark.parametrize(
    "caller,expected_service_fees,test_id",
    CALLER_SERVICE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_fees_by_caller_zero_filing_fee_without_service_fee(
    session, client, jwt, app, caller, expected_service_fees, test_id
):
    """No service fee configured should return zero for all callers."""
    corp_type, filing_type = generate_fee_schedule("ZNO", filing_amount=0, service_amount=None, with_distribution=False)

    rv = call_get_fees(client, get_headers(jwt, caller), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == 0
    assert rv.json.get("serviceFees") == 0


@pytest.mark.parametrize(
    "caller,expected_service_fees,test_id",
    CALLER_SERVICE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_invoice_by_caller_standard_schedule(session, client, jwt, app, caller, expected_service_fees, test_id):
    """Assert invoice creation applies the same caller service fee rules as the fees route."""
    corp_type, filing_type = generate_fee_schedule(f"IS{caller[:1].upper()}")

    rv = call_post_invoice(client, get_headers(jwt, caller), corp_type, filing_type)

    assert rv.status_code == 201
    assert rv.json.get("serviceFees") == expected_service_fees
    assert rv.json.get("total") == FILING_FEE_AMOUNT + expected_service_fees


@pytest.mark.parametrize(
    "caller,expected_service_fees,test_id",
    CALLER_SERVICE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_invoice_by_caller_zero_filing_fee_with_service_fee(
    session, client, jwt, app, caller, expected_service_fees, test_id
):
    """Assert zero dollar filings return appropriate service fees by caller type."""
    corp_type, filing_type = generate_fee_schedule(f"IZ{caller[:1].upper()}", filing_amount=0)

    rv = call_post_invoice(client, get_headers(jwt, caller), corp_type, filing_type)

    assert rv.status_code == 201
    assert rv.json.get("serviceFees") == expected_service_fees
    assert rv.json.get("total") == expected_service_fees


def test_exclude_service_fees_role_requires_system_role(session, client, jwt, app):
    """Assert exclude_service_fees alone without SYSTEM role does not exclude service fee."""
    corp_type, filing_type = generate_fee_schedule("EXC", with_distribution=False)
    headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(roles=[Role.EXCLUDE_SERVICE_FEES.value]), token_header)}",
        "content-type": "application/json",
    }

    rv = call_get_fees(client, headers, corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("serviceFees") == SERVICE_FEE_AMOUNT


@pytest.mark.parametrize(
    "caller,expected_filing_fees,test_id",
    [
        ("staff", 0, "staff_waive_fee_applies"),
        ("general", FILING_FEE_AMOUNT, "non_staff_waive_fee_ignored"),
    ],
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_fees_waive_applies_for_staff_only(session, client, jwt, app, caller, expected_filing_fees, test_id):
    """Assert waive fees is ignored for non staff users."""
    corp_type, filing_type = generate_fee_schedule(f"WV{caller[:1].upper()}", with_distribution=False)

    rv = call_get_fees(client, get_headers(jwt, caller), corp_type, filing_type, query="?waiveFees=true")

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == expected_filing_fees


def test_invoice_waive_rejected_for_non_staff(session, client, jwt, app):
    """Assert invoice creation rejects a waive fees for non-staff."""
    corp_type, filing_type = generate_fee_schedule("WVR")

    rv = call_post_invoice(client, get_headers(jwt, "general"), corp_type, filing_type, waiveFees=True)

    assert rv.status_code == 401
    assert rv.json.get("type") == "FEE_OVERRIDE_NOT_ALLOWED"


def test_invoice_waive_zeroes_filing_priority_and_future_effective(session, client, jwt, app):
    """A staff waiver zeroes priority and future effective fees."""
    corp_type, filing_type = generate_fee_schedule("WPRIOFUT", priority_amount=10, future_amount=20)

    rv = call_post_invoice(
        client,
        get_headers(jwt, "staff"),
        corp_type,
        filing_type,
        waiveFees=True,
        priority=True,
        futureEffective=True,
    )

    assert rv.status_code == 201
    line_item = rv.json.get("lineItems")[0]
    assert line_item.get("filingFees") == 0
    assert line_item.get("priorityFees") == 0
    assert line_item.get("futureEffectiveFees") == 0
    assert rv.json.get("total") == 0

    line_item = PaymentLineItemModel.query.filter_by(invoice_id=rv.json.get("id")).one()
    assert line_item.waived_fees == FILING_FEE_AMOUNT + 10 + 20
    assert line_item.waived_by is not None


ACCOUNT_OVERRIDE_FEE_MATRIX = [
    ("OVB", False, NO_FEE_CODE, 0, 0, "override_zeroes_filing_and_service"),
    ("OVN", True, None, FILING_FEE_AMOUNT, SERVICE_FEE_AMOUNT, "null_service_fee_code_falls_back_to_schedule"),
    ("OVZ", True, NO_FEE_CODE, FILING_FEE_AMOUNT, 0, "zero_service_fee_code_suppresses_service_fee"),
]


@pytest.mark.parametrize(
    "code,apply_filing_fees,service_fee_code,expected_filing_fees,expected_service_fees,test_id",
    ACCOUNT_OVERRIDE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_fees_account_override(  # pylint: disable=too-many-arguments
    session,
    client,
    jwt,
    app,
    code,
    apply_filing_fees,
    service_fee_code,
    expected_filing_fees,
    expected_service_fees,
    test_id,
):
    """Assert fees applies the account override."""
    corp_type, filing_type = generate_fee_schedule(code, product=BUSINESS_SEARCH, with_distribution=False)
    generate_payment_account(
        "8001", product=BUSINESS_SEARCH, apply_filing_fees=apply_filing_fees, service_fee_code=service_fee_code
    )

    rv = call_get_fees(client, get_headers(jwt, "general", account_id="8001"), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == expected_filing_fees
    assert rv.json.get("serviceFees") == expected_service_fees


def test_account_override_scoped_to_product(session, client, jwt, app):
    """Assert override is applied to one product."""
    corp_type, filing_type = generate_fee_schedule("OVU", product="OTHER_PRODUCT", with_distribution=False)
    generate_payment_account("8002", product=BUSINESS_SEARCH, apply_filing_fees=False, service_fee_code=NO_FEE_CODE)

    rv = call_get_fees(client, get_headers(jwt, "general", account_id="8002"), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == FILING_FEE_AMOUNT
    assert rv.json.get("serviceFees") == SERVICE_FEE_AMOUNT


# --- variable schedules -----------------------------------------------------------


def test_fees_variable_schedule_returns_configured_amount(session, client, jwt, app):
    """The fees route has no way to supply an amount, so it returns the configured one."""
    corp_type, filing_type = generate_fee_schedule("VRF", variable=True, with_distribution=False)

    rv = call_get_fees(client, get_headers(jwt, "general"), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == FILING_FEE_AMOUNT


VARIABLE_FEE_MATRIX = [
    ("VRU", {"fee": 250}, 250, "request_fee_replaces_filing_fee"),
    ("VRO", {}, 0, "omitted_fee_defaults_to_zero"),
]


@pytest.mark.parametrize(
    "code,overrides,expected_filing_fees,test_id",
    VARIABLE_FEE_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_invoice_variable_fee(session, client, jwt, app, code, overrides, expected_filing_fees, test_id):
    """Assert the request amount replaces the filing fee and the service fee stays as configured."""
    corp_type, filing_type = generate_fee_schedule(code, variable=True)

    rv = call_post_invoice(client, get_headers(jwt, "general"), corp_type, filing_type, **overrides)

    assert rv.status_code == 201
    assert rv.json.get("lineItems")[0].get("filingFees") == expected_filing_fees
    assert rv.json.get("serviceFees") == SERVICE_FEE_AMOUNT
    assert rv.json.get("total") == expected_filing_fees + SERVICE_FEE_AMOUNT


def test_invoice_variable_filing_fee_unaffected_by_waive(session, client, jwt, app):
    """Assert the variable overrides the fee waiver."""
    corp_type, filing_type = generate_fee_schedule("VRW", variable=True)

    rv = call_post_invoice(client, get_headers(jwt, "staff"), corp_type, filing_type, fee=250, waiveFees=True)

    assert rv.status_code == 201
    assert rv.json.get("lineItems")[0].get("filingFees") == 250


def test_zero_filing_fee_still_charges_priority_and_future_effective(session, client, jwt, app):
    """Assert additional fees are still charged on a zero filing fee schedule."""
    corp_type, filing_type = generate_fee_schedule(
        "ZPF", filing_amount=0, priority_amount=10, future_amount=20, with_distribution=False
    )

    rv = call_get_fees(
        client, get_headers(jwt, "general"), corp_type, filing_type, query="?priority=true&futureEffective=true"
    )

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == 0
    assert rv.json.get("priorityFees") == 10
    assert rv.json.get("futureEffectiveFees") == 20
    assert rv.json.get("total") == 10 + 20 + SERVICE_FEE_AMOUNT


SERVICE_FEE_GST_MATRIX = [
    ("XGC", "general", None, SERVICE_FEE_AMOUNT, 0.08, "service_fee_charged_carries_gst"),
    ("XGS", "staff", None, 0, 0, "staff_exemption"),
    ("XGE", "system_excluded", None, 0, 0, "exclude_service_fees_role"),
    ("XGZ", "general", "8007", 0, 0, "zero_amount_account_override"),
]


@pytest.mark.parametrize(
    "code,caller,account_id,expected_service_fees,expected_service_fee_gst,test_id",
    SERVICE_FEE_GST_MATRIX,
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_fees_service_fee_gst(  # pylint: disable=too-many-arguments
    session,
    client,
    jwt,
    app,
    code,
    caller,
    account_id,
    expected_service_fees,
    expected_service_fee_gst,
    test_id,
):
    """Assert zero filing fee can still properly charge service fees with GST when relevant."""
    corp_type, filing_type = generate_fee_schedule(
        code,
        filing_amount=0,
        service_fees_gst_added=True,
        product=BUSINESS_SEARCH,
        with_distribution=False,
    )
    if account_id:
        generate_payment_account(account_id, product=BUSINESS_SEARCH, service_fee_code=NO_FEE_CODE)

    rv = call_get_fees(client, get_headers(jwt, caller, account_id=account_id), corp_type, filing_type)

    assert rv.status_code == 200
    assert rv.json.get("serviceFees") == expected_service_fees
    assert rv.json.get("tax").get("serviceFeeGst") == expected_service_fee_gst
    assert rv.json.get("total") == expected_service_fees + expected_service_fee_gst


def test_statutory_gst_applies_to_priority_on_zero_filing_fee(session, client, jwt, app):
    """Assert GST is charged on filing + priority + future effective, not the filing fee alone."""
    corp_type, filing_type = generate_fee_schedule(
        "ZSG", filing_amount=0, priority_amount=10, statutory_fees_gst_added=True, with_distribution=False
    )

    rv = call_get_fees(client, get_headers(jwt, "general"), corp_type, filing_type, query="?priority=true")

    assert rv.status_code == 200
    assert rv.json.get("filingFees") == 0
    assert rv.json.get("tax").get("filingFeeGst") == 0.5
