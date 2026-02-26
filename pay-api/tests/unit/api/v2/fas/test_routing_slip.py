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

"""Tests for the v2 routing slip GET endpoint.

Verifies that the v2 route returns invoice composite model data for refunds
while the v1 route does are without those fields.
"""

import json
from datetime import UTC, datetime

import pytest

from pay_api.models import PaymentAccount
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.refund import Refund as RefundModel
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, RefundStatus, RefundType, Role
from tests.utilities.base_test import factory_invoice, get_claims, get_routing_slip_request, token_header

REFUND_FIELDS = {"latestRefundId", "latestRefundStatus", "fullRefundable", "partialRefundable"}


def _create_routing_slip_with_invoice(client, jwt, rs_number: str):
    """Helper: create a routing slip and attach one INTERNAL-payment invoice to it.

    Returns (headers, rs_number).
    """
    token = jwt.create_jwt(
        get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]),
        token_header,
    )
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/fas/routing-slips",
        data=json.dumps(get_routing_slip_request(number=rs_number)),
        headers=headers,
    )
    assert rv.status_code == 201, f"Expected 201 creating routing slip, got {rv.status_code}"

    payment_account_id = rv.json.get("paymentAccount").get("id")
    invoice = factory_invoice(
        PaymentAccount(id=payment_account_id),
        routing_slip=rs_number,
        payment_method_code=PaymentMethod.INTERNAL.value,
        total=100,
        paid=100,
    )
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.save()

    return headers, rs_number


@pytest.mark.parametrize("refund_status", [RefundStatus.APPROVAL_NOT_REQUIRED.value, RefundStatus.APPROVED.value])
def test_get_routing_slip_v2_approval(session, client, jwt, refund_status):
    """Assert invoice composite model refund fields are returned for approval end states."""
    headers, rs_number = _create_routing_slip_with_invoice(client, jwt, "123456789")

    rv = client.get(f"/api/v2/fas/routing-slips/{rs_number}", headers=headers)
    assert rv.status_code == 200

    invoices = rv.json.get("invoices")
    assert invoices is not None
    assert len(invoices) == 1

    invoice = invoices[0]
    assert invoice["latestRefundId"] is None
    assert invoice["latestRefundStatus"] is None
    assert invoice["fullRefundable"] is True
    assert invoice["partialRefundable"] is False
    assert invoice["refund"] == 0

    refund = RefundModel(
        type=RefundType.INVOICE.value,
        status=refund_status,
        invoice_id=invoice["id"],
        requested_by="test_user",
        requested_date=datetime.now(tz=UTC),
    ).save()
    invoice_model = InvoiceModel.find_by_id(invoice["id"])
    invoice_model.invoice_status_code = InvoiceStatus.REFUNDED.value
    invoice_model.refund = 100
    invoice_model.save()

    refund = RefundModel.find_by_id(refund.id)
    rv = client.get(f"/api/v2/fas/routing-slips/{rs_number}", headers=headers)
    assert rv.status_code == 200

    invoices = rv.json.get("invoices")
    assert invoices is not None
    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice["latestRefundId"] == refund.id
    assert invoice["latestRefundStatus"] == refund_status
    assert invoice["fullRefundable"] is False
    assert invoice["partialRefundable"] is False
    assert invoice["refund"] == 100


@pytest.mark.parametrize("refund_status", [RefundStatus.PENDING_APPROVAL.value, RefundStatus.DECLINED.value])
def test_get_routing_slip_v2_refund_incomplete(session, client, jwt, refund_status):
    """Assert invoice composite model refund fields are returned for refund incomplete states."""
    headers, rs_number = _create_routing_slip_with_invoice(client, jwt, "123456789")

    rv = client.get(f"/api/v2/fas/routing-slips/{rs_number}", headers=headers)
    assert rv.status_code == 200

    invoices = rv.json.get("invoices")
    assert invoices is not None
    assert len(invoices) == 1

    invoice = invoices[0]
    assert invoice["latestRefundId"] is None
    assert invoice["latestRefundStatus"] is None
    assert invoice["fullRefundable"] is True
    assert invoice["partialRefundable"] is False
    assert invoice["refund"] == 0

    refund = RefundModel(
        type=RefundType.INVOICE.value,
        status=refund_status,
        invoice_id=invoice["id"],
        requested_by="test_user",
        requested_date=datetime.now(tz=UTC),
    ).save()

    refund = RefundModel.find_by_id(refund.id)
    rv = client.get(f"/api/v2/fas/routing-slips/{rs_number}", headers=headers)
    assert rv.status_code == 200

    invoices = rv.json.get("invoices")
    assert invoices is not None
    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice["latestRefundId"] == refund.id
    assert invoice["latestRefundStatus"] == refund_status
    assert invoice["fullRefundable"] is True
    assert invoice["partialRefundable"] is False
    assert invoice["refund"] == 0


def test_get_routing_slip_v1_invoices_without_refund_data(session, client, jwt):
    """Assert invoice composite model refund fields are NOT returned."""
    headers, rs_number = _create_routing_slip_with_invoice(client, jwt, "123456789")

    rv = client.get(f"/api/v1/fas/routing-slips/{rs_number}", headers=headers)
    assert rv.status_code == 200

    invoices = rv.json.get("invoices")
    assert invoices is not None, "invoices key must be present in v1 response"
    assert len(invoices) == 1

    invoice = invoices[0]
    unexpected = REFUND_FIELDS & invoice.keys()
    assert not unexpected, f"v1 invoice must NOT contain composite fields: {unexpected}"


def test_get_routing_slip_v2_empty_invoice_list(session, client, jwt):
    """Assert empty invoice list works on v2."""
    token = jwt.create_jwt(
        get_claims(roles=[Role.FAS_CREATE.value, Role.FAS_VIEW.value]),
        token_header,
    )
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rs_number = "123456789"
    rv = client.post(
        "/api/v1/fas/routing-slips",
        data=json.dumps(get_routing_slip_request(number=rs_number)),
        headers=headers,
    )
    assert rv.status_code == 201

    rv = client.get(f"/api/v2/fas/routing-slips/{rs_number}", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("invoices") == [], "invoices should be an empty list when none exist"
