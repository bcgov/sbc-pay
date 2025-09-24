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

"""Tests to assure the account payments endpoint.

Test-Suite to ensure that the /accounts/{accountId}/payments/queries endpoint is working as expected.
"""

import json
from unittest.mock import patch

import pytest
from faker import Faker

from pay_api.models.invoice import Invoice
from pay_api.models.payment_account import PaymentAccount
from pay_api.utils.enums import Role, RolePattern
from tests.utilities.base_test import (
    factory_corp_type_model,
    factory_distribution_code,
    factory_distribution_link,
    factory_fee_model,
    factory_fee_schedule_model,
    factory_filing_type_model,
    get_claims,
    get_payment_request,
    token_header,
)

fake = Faker()


@pytest.mark.parametrize(
    "product_role, product_role2, has_product_refund_viewer,response_status_code",
    [
        ("viewer_no_products", None, True, 403),
        ("incorrect_role", None, False, 403),
        ("bca" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("btr" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("business" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("business_search" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("cso" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("esra" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("mhr" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("ppr" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("rppr" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("rpt" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("sofi" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("strr" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
        ("vs" + RolePattern.PRODUCT_VIEW_TRANSACTION.value, None, True, 200),
    ],
)
def test_product_purchase_history(
    session, client, jwt, app, product_role, product_role2, has_product_refund_viewer, response_status_code
):
    """Assert account transaction filter by product roles are working."""
    product_token, staff_token = setup_tokens(jwt, product_role, has_product_refund_viewer)
    product_code = product_role.replace(RolePattern.PRODUCT_VIEW_TRANSACTION.value, "").upper()
    pay_account = setup_transactions(client, jwt, product_code)

    product_role_headers = {"Authorization": f"Bearer {product_token}", "content-type": "application/json"}
    staff_headers = {"Authorization": f"Bearer {staff_token}", "content-type": "application/json"}

    for payload in [{}, {"excludeCounts": True}]:
        rv = client.post(
            f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?viewAll=true",
            data=json.dumps(payload),
            headers=product_role_headers,
        )

        assert rv.status_code == response_status_code
        if response_status_code == 200:
            # Should only return result with our role product code
            assert rv.json
            assert len(rv.json["items"]) == 1
            assert rv.json["items"][0]["product"] == product_code

            # Confirm viewAll filtering works for view_all_transactions which doesn't apply product filtering
            with patch("pay_api.resources.v1.account.check_auth") as mock_auth:
                rv = client.post(
                    f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?viewAll=true",
                    data=json.dumps(payload),
                    headers=staff_headers,
                )
                mock_auth.assert_called_once()
                assert rv.status_code == response_status_code
                assert rv.json
                assert len(rv.json["items"]) == 2


def test_product_claim_purchase_history(session, client, jwt, app):
    """Assert account transaction filter by product claim is working."""
    product_code = "BCA"
    product_claim_token = jwt.create_jwt(
        get_claims(product_code=product_code),
        token_header,
    )

    pay_account = setup_transactions(client, jwt, product_code)
    headers = {"Authorization": f"Bearer {product_claim_token}", "content-type": "application/json"}

    for payload in [{}, {"excludeCounts": True}]:
        with patch("pay_api.resources.v1.account.check_auth") as mock_auth:
            rv = client.post(
                f"/api/v1/accounts/{pay_account.auth_account_id}/payments/queries?viewAll=true",
                data=json.dumps(payload),
                headers=headers,
            )

            assert rv.status_code == 200
            assert rv.json
            assert len(rv.json["items"]) == 1
            assert rv.json["items"][0]["product"] == product_code
            mock_auth.assert_called_once()


def setup_tokens(jwt, product_role: str, has_product_refund_viewer: bool) -> tuple:
    """Set up different role tokens to verify search results."""
    product_viewer_claim_roles = [product_role]
    if has_product_refund_viewer:
        product_viewer_claim_roles.append(Role.PRODUCT_REFUND_VIEWER.value)

    product_token = jwt.create_jwt(
        get_claims(roles=product_viewer_claim_roles, product_code=None),
        token_header,
    )

    staff_token = jwt.create_jwt(
        get_claims(roles=[Role.STAFF.value, Role.VIEW_ALL_TRANSACTIONS.value], product_code=None),
        token_header,
    )

    return product_token, staff_token


def setup_transactions(client, jwt, product_code):
    """Set up transaction data for different products."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    test_code = "TEST_CODE"
    distribution_code = factory_distribution_code(test_code).save()
    fee_schedule = factory_fee_schedule_model(
        filing_type=factory_filing_type_model(test_code, test_code),
        corp_type=factory_corp_type_model(test_code, test_code, product_code),
        fee_code=factory_fee_model(test_code, 100),
    )
    factory_distribution_link(
        distribution_code.distribution_code_id,
        fee_schedule.fee_schedule_id,
    ).save()

    payment_request = get_payment_request(corp_type=test_code, second_filing_type=test_code)
    payment_request["filingInfo"]["filingTypes"] = [{"filingTypeCode": test_code}]

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payment_request), headers=headers)
    assert rv.status_code == 201
    invoice = rv.json.get("id")
    assert invoice is not None

    # Set up data that will be filtered out with a non matching product code
    other_test_code = "OTHER_CODE"
    fee_schedule_other = factory_fee_schedule_model(
        filing_type=factory_filing_type_model(other_test_code, other_test_code),
        corp_type=factory_corp_type_model(other_test_code, other_test_code, other_test_code),
        fee_code=factory_fee_model(other_test_code, 100),
    )
    factory_distribution_link(
        distribution_code.distribution_code_id,
        fee_schedule_other.fee_schedule_id,
    ).save()

    payment_request = get_payment_request(corp_type=other_test_code, second_filing_type=other_test_code)
    payment_request["filingInfo"]["filingTypes"] = [{"filingTypeCode": other_test_code}]

    rv = client.post("/api/v1/payment-requests", data=json.dumps(payment_request), headers=headers)
    assert rv.status_code == 201
    invoice_id = rv.json.get("id")
    assert invoice_id is not None

    invoice = Invoice.find_by_id(invoice_id)
    pay_account = PaymentAccount.find_by_id(invoice.payment_account_id)
    return pay_account
