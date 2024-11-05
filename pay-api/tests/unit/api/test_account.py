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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from faker import Faker
from requests.exceptions import ConnectionError

from pay_api.exceptions import ServiceUnavailableException
from pay_api.models.cfs_account import CfsAccount as CfsAccountModel
from pay_api.models.distribution_code import DistributionCodeLink as DistributionCodeLinkModel
from pay_api.models.fee_schedule import FeeSchedule
from pay_api.models.invoice import Invoice
from pay_api.models.payment_account import PaymentAccount
from pay_api.schemas import utils as schema_utils
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, Role
from tests.utilities.base_test import (
    factory_invoice,
    get_auth_basic_user,
    get_basic_account_payload,
    get_claims,
    get_gov_account_payload,
    get_gov_account_payload_with_no_revenue_account,
    get_linked_pad_account_payload,
    get_payment_request,
    get_payment_request_for_cso,
    get_payment_request_with_folio_number,
    get_payment_request_with_service_fees,
    get_premium_account_payload,
    get_unlinked_pad_account_payload,
    token_header,
)

fake = Faker()


def test_account_purchase_history(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_folio_number()),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    invoice.disbursement_date = datetime.now(tz=timezone.utc)
    invoice.disbursement_reversal_date = datetime.now(tz=timezone.utc)
    invoice.save()

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 200
    # Note this is used by CSO, they need these fields at a minimum.
    assert rv.json
    invoice = rv.json.get("items")[0]
    assert invoice
    required_fields = [
        "id",
        "corpTypeCode",
        "createdOn",
        "statusCode",
        "total",
        "serviceFees",
        "paid",
        "refund",
        "folioNumber",
        "createdName",
        "paymentMethod",
        "details",
        "businessIdentifier",
        "createdBy",
        "filingId",
        "disbursementReversalDate",
        "disbursementDate",
    ]

    for field in required_fields:
        assert field in invoice


def test_account_purchase_history_with_basic_account(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    pay_account = PaymentAccountService.find_account(get_auth_basic_user())

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 200


def test_account_purchase_history_pagination(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    for i in range(10):
        rv = client.post(
            "/api/v1/payment-requests",
            data=json.dumps(get_payment_request()),
            headers=headers,
        )

    invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?page=1&limit=5",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json.get("total") == 10
    assert len(rv.json.get("items")) == 5


def test_account_purchase_history_with_service_account(session, client, jwt, app):
    """Assert that purchase history returns only invoices for that product."""
    # Point CSO fee schedule to a valid distribution code.
    fee_schedule_id = FeeSchedule.find_by_filing_type_and_corp_type("CSO", "CSBVFEE").fee_schedule_id
    DistributionCodeLinkModel(fee_schedule_id=fee_schedule_id, distribution_code_id=1).save()

    # Point PPR fee schedule to a valid distribution code.
    fee_schedule_id = FeeSchedule.find_by_filing_type_and_corp_type("PPR", "FSDIS").fee_schedule_id
    DistributionCodeLinkModel(fee_schedule_id=fee_schedule_id, distribution_code_id=1).save()

    # Create one invoice for CSO and one fpr BUSINESS.
    # Then query without any filter and make sure only CSO invoice is returned for service account with CSO product_code
    for corp_filing_type in (["CSO", "CSBVFEE"], ["PPR", "FSDIS"]):
        token = jwt.create_jwt(
            get_claims(roles=[Role.SYSTEM.value], product_code=corp_filing_type[0]),
            token_header,
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "content-type": "application/json",
        }
        rv = client.post(
            "/api/v1/payment-requests",
            data=json.dumps(
                get_payment_request_with_service_fees(corp_type=corp_filing_type[0], filing_type=corp_filing_type[1])
            ),
            headers=headers,
        )

    invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)

    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value], product_code="CSO"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?page=1&limit=5",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json.get("total") == 1
    assert len(rv.json.get("items")) == 1
    assert rv.json.get("items")[0]["corpTypeCode"] == "CSO"


def test_payment_request_for_cso_with_service_account(session, client, jwt, app):
    """Assert Service charge is calculated based on quantity."""
    # Point CSO fee schedule to a valid distribution code.
    fee_schedule_id = FeeSchedule.find_by_filing_type_and_corp_type("CSO", "CSBVFEE").fee_schedule_id
    DistributionCodeLinkModel(fee_schedule_id=fee_schedule_id, distribution_code_id=1).save()

    quantity = 2
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value], product_code="CSO"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_for_cso(quantity)),
        headers=headers,
    )
    rv2 = client.get("/api/v1/fees/CSO/CSBVFEE", headers=headers)
    assert rv2.status_code == 200
    assert rv.status_code == 201
    assert rv.json.get("lineItems")[0]["serviceFees"] == rv2.json.get("serviceFees") * quantity


def test_account_purchase_history_invalid_request(session, client, jwt, app):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    search_filter = {"businessIdentifier": 1111}

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?page=1&limit=5",
        data=json.dumps(search_filter),
        headers=headers,
    )

    assert rv.status_code == 400
    assert schema_utils.validate(rv.json, "problem")[0]


def test_account_purchase_history_forbidden(session, client, jwt, app):
    """Assert that the endpoint returns 403 when trying to view all transactions if not authorized."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?viewAll=true",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 403


def test_account_purchase_history_export_as_csv(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": "text/csv",
    }

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/reports",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 201


def test_account_purchase_history_export_as_pdf(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": "application/pdf",
    }

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/reports",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 201


def test_account_purchase_history_export_invalid_request(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": "application/pdf",
    }

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/reports",
        data=json.dumps({"businessIdentifier": 1111}),
        headers=headers,
    )

    assert rv.status_code == 400


def test_account_purchase_history_default_list(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Create 11 payments
    for i in range(11):
        rv = client.post(
            "/api/v1/payment-requests",
            data=json.dumps(get_payment_request()),
            headers=headers,
        )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries",
        data=json.dumps({}),
        headers=headers,
    )

    assert rv.status_code == 200
    # Assert the total is coming as 10 which is the value of default TRANSACTION_REPORT_DEFAULT_TOTAL
    assert rv.json.get("total") == 10


def test_bad_id_payment_queries(session, client, jwt, app):
    """Assert testing a string inside of the route doesn't work."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts/undefined/payments/queries",
        data=json.dumps({}),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("invalidParams") == "account_number"


def test_basic_account_creation(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload()),
        headers=headers,
    )

    assert rv.status_code == 201


def test_basic_account_creation_unauthorized(session, client, jwt, app):
    """Assert that the endpoint returns 401."""
    token = jwt.create_jwt(get_claims(role=Role.EDITOR.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload()),
        headers=headers,
    )

    assert rv.status_code == 401


def test_premium_account_creation(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_premium_account_payload()),
        headers=headers,
    )

    assert rv.status_code == 201


def test_premium_account_update_bcol_pad(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payload = get_premium_account_payload()
    rv = client.post("/api/v1/accounts", data=json.dumps(payload), headers=headers)

    auth_account_id = rv.json.get("accountId")

    rv = client.get(f"/api/v1/accounts/{auth_account_id}", headers=headers)
    assert rv.json.get("accountId") == auth_account_id

    # assert switching to PAD returns bank details
    pad_account_details = get_linked_pad_account_payload(account_id=int(auth_account_id))

    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps(pad_account_details),
        headers=headers,
    )

    assert rv.status_code == 200

    assert rv.json.get("futurePaymentMethod") == PaymentMethod.PAD.value
    assert rv.json.get("bankTransitNumber") == pad_account_details.get("bankTransitNumber")

    # Assert switching to bcol returns no bank details
    rv = client.put(f"/api/v1/accounts/{auth_account_id}", data=json.dumps(payload), headers=headers)

    assert rv.json.get("futurePaymentMethod") is None
    assert rv.json.get("bankTransitNumber") is None
    assert rv.json.get("branchName") == payload["branchName"]


def test_premium_duplicate_account_creation(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    client.post(
        "/api/v1/accounts",
        data=json.dumps(get_premium_account_payload()),
        headers=headers,
    )

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_premium_account_payload()),
        headers=headers,
    )

    assert rv.status_code == 400


def test_premium_account_update(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_premium_account_payload()),
        headers=headers,
    )

    auth_account_id = rv.json.get("accountId")

    rv = client.get(f"/api/v1/accounts/{auth_account_id}", headers=headers)
    assert rv.json.get("accountId") == auth_account_id

    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps(get_premium_account_payload()),
        headers=headers,
    )

    assert rv.status_code == 200


def test_create_pad_account_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Mock ServiceUnavailableException
    with patch(
        "pay_api.services.oauth_service.OAuthService.post",
        side_effect=ServiceUnavailableException(ConnectionError("mocked error")),
    ):
        rv = client.post(
            "/api/v1/accounts",
            data=json.dumps(get_unlinked_pad_account_payload()),
            headers=headers,
        )

        assert rv.status_code == 202


def test_create_pad_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_unlinked_pad_account_payload()),
        headers=headers,
    )

    assert rv.status_code == 202


def test_create_online_banking_account_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Mock ServiceUnavailableException
    with patch(
        "pay_api.services.oauth_service.OAuthService.post",
        side_effect=ServiceUnavailableException(ConnectionError("mocked error")),
    ):
        rv = client.post(
            "/api/v1/accounts",
            data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
            headers=headers,
        )

        assert rv.status_code == 202


def test_create_online_banking_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
        headers=headers,
    )

    assert rv.status_code == 202


def test_create_pad_update_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Create account first
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_unlinked_pad_account_payload()),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")

    # Mock ServiceUnavailableException
    with patch(
        "pay_api.services.oauth_service.OAuthService.post",
        side_effect=ServiceUnavailableException(ConnectionError("mocked error")),
    ):
        rv = client.put(
            f"/api/v1/accounts/{auth_account_id}",
            data=json.dumps(get_unlinked_pad_account_payload(bank_account="11111111")),
            headers=headers,
        )

        assert rv.status_code == 503


def test_update_pad_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_unlinked_pad_account_payload()),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps(get_unlinked_pad_account_payload(bank_account="11111111")),
        headers=headers,
    )

    assert rv.status_code == 200


def test_switch_eft_account_when_cfs_up(session, client, jwt, app, admin_users_mock):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.PAD.value)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.EFT.value)),
        headers=headers,
    )
    # 202 and 200, 202 for when there is a CFS account PENDING.
    # 200 when the CFS account is invalid etc.
    assert rv.status_code == 202


def test_update_online_banking_account_when_cfs_down(session, client, jwt, app):
    """Assert that the payment records are created with 200, as there is no CFS update."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    # Mock ServiceUnavailableException
    with patch(
        "pay_api.services.oauth_service.OAuthService.post",
        side_effect=ServiceUnavailableException(ConnectionError("mocked error")),
    ):
        rv = client.put(
            f"/api/v1/accounts/{auth_account_id}",
            data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
            headers=headers,
        )

        assert rv.status_code == 202


def test_update_online_banking_account_when_cfs_up(session, client, jwt, app):
    """Assert that the payment records are created with 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
        headers=headers,
    )

    assert rv.status_code == 202


def test_update_name(session, client, jwt, app):
    """Assert that the payment records are created with 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.ONLINE_BANKING.value)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps({"accountName": fake.name(), "branchName": fake.name()}),
        headers=headers,
    )

    assert rv.status_code == 202


def test_account_get_by_system(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_unlinked_pad_account_payload()),
        headers=headers,
    )

    auth_account_id = rv.json.get("accountId")

    rv = client.get(f"/api/v1/accounts/{auth_account_id}", headers=headers)
    assert rv.json.get("cfsAccount").get("bankTransitNumber")
    assert rv.json.get("cfsAccount").get("bankAccountNumber")
    assert rv.json.get("cfsAccount").get("bankInstitutionNumber")


def test_account_get_by_user(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    account = get_unlinked_pad_account_payload()
    rv = client.post("/api/v1/accounts", data=json.dumps(account), headers=headers)

    auth_account_id = rv.json.get("accountId")

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.get(f"/api/v1/accounts/{auth_account_id}", headers=headers)
    assert rv.json.get("cfsAccount").get("bankTransitNumber")
    expected_bank_number = len(account.get("paymentInfo").get("bankAccountNumber")) * "X"
    assert rv.json.get("cfsAccount").get("bankAccountNumber") == expected_bank_number
    assert rv.json.get("cfsAccount").get("bankInstitutionNumber")


def test_create_gov_accounts(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post("/api/v1/accounts", data=json.dumps(get_gov_account_payload()), headers=headers)

    assert rv.status_code == 201


def test_create_and_delete_gov_accounts_with_account_fee(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post("/api/v1/accounts", data=json.dumps(get_gov_account_payload()), headers=headers)

    account_id = rv.json.get("accountId")

    # Create account fee details.
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_ACCOUNTS.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        f"/api/v1/accounts/{account_id}/fees",
        data=json.dumps(
            {
                "accountFees": [
                    {
                        "applyFilingFees": False,
                        "serviceFeeCode": "TRF01",
                        "product": "BUSINESS",
                    }
                ]
            }
        ),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json.get("accountFees")[0]["product"] == "BUSINESS"
    assert not rv.json.get("accountFees")[0]["applyFilingFees"]
    assert rv.json.get("accountFees")[0]["serviceFeeCode"] == "TRF01"

    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get(f"/api/v1/accounts/{account_id}/fees", headers=headers)

    assert rv.json.get("accountFees")[0]["product"] == "BUSINESS"
    assert not rv.json.get("accountFees")[0]["applyFilingFees"]
    assert rv.json.get("accountFees")[0]["serviceFeeCode"] == "TRF01"

    rv = client.delete(f"/api/v1/accounts/{account_id}/fees", headers=headers)
    assert rv.status_code == 204

    rv = client.get(f"/api/v1/accounts/{account_id}/fees", headers=headers)
    assert len(rv.json.get("accountFees")) == 0


def test_update_gov_accounts_with_account_fee(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post("/api/v1/accounts", data=json.dumps(get_gov_account_payload()), headers=headers)

    account_id = rv.json.get("accountId")

    # Create account fee details.
    token = jwt.create_jwt(get_claims(role=Role.MANAGE_ACCOUNTS.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        f"/api/v1/accounts/{account_id}/fees",
        data=json.dumps(
            {
                "accountFees": [
                    {
                        "applyFilingFees": False,
                        "serviceFeeCode": "TRF01",
                        "product": "BUSINESS",
                    }
                ]
            }
        ),
        headers=headers,
    )

    assert rv.status_code == 200

    # PUT this with changes
    rv = client.put(
        f"/api/v1/accounts/{account_id}/fees/BUSINESS",
        data=json.dumps({"applyFilingFees": True, "serviceFeeCode": "TRF02"}),
        headers=headers,
    )

    assert rv.json["product"] == "BUSINESS"
    assert rv.json["applyFilingFees"]
    assert rv.json["serviceFeeCode"] == "TRF02"


def test_update_gov_accounts(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    account_id = 123
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_gov_account_payload_with_no_revenue_account(account_id=account_id)),
        headers=headers,
    )
    assert rv.status_code == 201

    project_code = "1111111"
    rv = client.put(
        f"/api/v1/accounts/{account_id}",
        data=json.dumps(get_gov_account_payload(account_id=account_id, project_code=project_code)),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json["revenueAccount"]["projectCode"] == project_code

    # update again with new JV details
    project_code = "2222222"
    rv = client.put(
        f"/api/v1/accounts/{account_id}",
        data=json.dumps(get_gov_account_payload(account_id=account_id, project_code=project_code)),
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json["revenueAccount"]["projectCode"] == project_code


def test_account_delete(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_premium_account_payload()),
        headers=headers,
    )

    auth_account_id = rv.json.get("accountId")

    rv = client.delete(f"/api/v1/accounts/{auth_account_id}", headers=headers)
    assert rv.status_code == 204


@pytest.mark.parametrize(
    "pay_load, is_cfs_account_expected, expected_response_status, roles",
    [
        (
            get_unlinked_pad_account_payload(),
            True,
            201,
            [Role.SYSTEM.value, Role.CREATE_SANDBOX_ACCOUNT.value],
        ),
        (
            get_premium_account_payload(),
            False,
            201,
            [Role.SYSTEM.value, Role.CREATE_SANDBOX_ACCOUNT.value],
        ),
        (get_premium_account_payload(), False, 403, [Role.SYSTEM.value]),
    ],
)
def test_create_sandbox_accounts(
    session,
    client,
    jwt,
    app,
    pay_load,
    is_cfs_account_expected,
    expected_response_status,
    roles,
):
    """Assert that the payment records are created with 202."""
    token = jwt.create_jwt(get_claims(roles=roles), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post("/api/v1/accounts?sandbox=true", data=json.dumps(pay_load), headers=headers)

    assert rv.status_code == expected_response_status
    if is_cfs_account_expected:
        assert rv.json["cfsAccount"]["status"] == CfsAccountStatus.ACTIVE.value


def test_search_eft_accounts(session, client, jwt, app, admin_users_mock):
    """Assert that the endpoint returns 200."""
    data = get_premium_account_payload(payment_method=PaymentMethod.EFT.value)
    token = jwt.create_jwt(get_claims(roles=[Role.SYSTEM.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post("/api/v1/accounts", data=json.dumps(data), headers=headers)
    assert rv.status_code == 202
    auth_account_id = rv.json.get("accountId")
    client.patch(
        f"/api/v1/accounts/{auth_account_id}/eft",
        data=json.dumps({"eftEnabled": True}),
        headers=headers,
    )

    # This should be excluded from results, because the mock from auth-api indicates this is non-active.
    data = get_premium_account_payload(payment_method=PaymentMethod.EFT.value, account_id=911)
    rv = client.post("/api/v1/accounts", data=json.dumps(data), headers=headers)
    assert rv.status_code == 202
    assert rv.json.get("accountId") == "911"
    client.patch(
        "/api/v1/accounts/911/eft",
        data=json.dumps({"eftEnabled": True}),
        headers=headers,
    )

    payment_account_id = rv.json.get("id")
    cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account_id, PaymentMethod.EFT.value)
    cfs_account.status = CfsAccountStatus.INACTIVE.value
    cfs_account.save()

    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    # Name
    rv = client.get("/api/v1/accounts/search/eft?searchText=Test", headers=headers)
    assert rv.status_code == 200
    assert len(rv.json.get("items")) == 1
    assert rv.json.get("items")[0].get("accountId") == auth_account_id

    # Branch Name
    rv = client.get("/api/v1/accounts/search/eft?searchText=Branch", headers=headers)
    assert rv.status_code == 200
    assert len(rv.json.get("items")) == 1
    assert rv.json.get("items")[0].get("accountId") == auth_account_id

    rv = client.get(f"/api/v1/accounts/search/eft?searchText={auth_account_id}", headers=headers)
    assert rv.status_code == 200
    assert len(rv.json.get("items")) == 1
    assert rv.json.get("items")[0].get("accountId") == auth_account_id


def test_switch_eft_account_when_outstanding_balance(session, client, jwt, app, admin_users_mock):
    """Assert outstanding balance check when switching away from EFT."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/accounts",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.EFT.value)),
        headers=headers,
    )
    auth_account_id = rv.json.get("accountId")
    payment_account_id = rv.json.get("id")
    payment_account: PaymentAccount = PaymentAccount.find_by_id(payment_account_id)

    factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=50,
        paid=0,
    ).save()

    rv = client.put(
        f"/api/v1/accounts/{auth_account_id}",
        data=json.dumps(get_basic_account_payload(payment_method=PaymentMethod.PAD.value)),
        headers=headers,
    )

    assert rv.status_code == 400
    assert rv.json["type"] == "EFT_SHORT_NAME_OUTSTANDING_BALANCE"
