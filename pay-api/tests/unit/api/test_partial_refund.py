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

"""Tests to assure the refund end-point can handle partial refunds.

Test-Suite to ensure that the refunds endpoint for partials is working as expected.
"""
import json
from datetime import datetime, timezone
from typing import List
from unittest.mock import patch

import pytest
from _decimal import Decimal

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundPartialLine
from pay_api.models import RefundsPartial as RefundPartialModel
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.refund import RefundService
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import InvoiceStatus, RefundsPartialType, Role
from pay_api.utils.errors import Error
from tests.utilities.base_test import get_claims, get_payment_request, token_header


def test_create_refund(session, client, jwt, app, monkeypatch):
    """Assert that the endpoint  returns 202."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inv_id = rv.json.get("id")
    invoice: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.save()

    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    client.patch(
        f"/api/v1/payment-requests/{inv_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_line_items: List[PaymentLineItemModel] = invoice.payment_line_items
    refund_amount = float(payment_line_items[0].filing_fees / 2)
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": refund_amount,
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    direct_pay_service = DirectPayService()
    base_paybc_response = _get_base_paybc_response()
    refund_partial = [
        RefundPartialLine(
            payment_line_item_id=payment_line_items[0].id,
            refund_amount=Decimal(refund_amount),
            refund_type=RefundsPartialType.BASE_FEES.value,
        )
    ]
    with patch("pay_api.services.direct_pay_service.DirectPayService.get") as mock_get:
        mock_get.return_value.ok = True
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = base_paybc_response
        payload = direct_pay_service.build_automated_refund_payload(invoice, refund_partial)
        assert payload
        assert payload["txnAmount"] == refund_partial[0].refund_amount
        assert payload["refundRevenue"][0]["lineNumber"] == "1"
        assert payload["refundRevenue"][0]["refundAmount"] == refund_partial[0].refund_amount

        rv = client.post(
            f"/api/v1/payment-requests/{inv_id}/refunds",
            data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
            headers=headers,
        )
        assert rv.status_code == 202
        assert rv.json.get("message") == REFUND_SUCCESS_MESSAGES["DIRECT_PAY.PAID"]
        assert RefundModel.find_by_invoice_id(inv_id) is not None

        refunds_partial: List[RefundPartialModel] = RefundService.get_refund_partials_by_invoice_id(inv_id)
        assert refunds_partial
        assert len(refunds_partial) == 1

        refund = refunds_partial[0]
        assert refund.id is not None
        assert refund.payment_line_item_id == payment_line_items[0].id
        assert refund.refund_amount == refund_amount
        assert refund.refund_type == RefundsPartialType.BASE_FEES.value

        invoice = InvoiceModel.find_by_id(invoice.id)
        assert invoice.invoice_status_code == InvoiceStatus.PAID.value
        assert invoice.refund_date.date() == datetime.now(tz=timezone.utc).date()
        assert invoice.refund == refund_amount


def test_create_refund_fails(session, client, jwt, app, monkeypatch):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inv_id = rv.json.get("id")

    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    client.patch(
        f"/api/v1/payment-requests/{inv_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )

    invoice = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.APPROVED.value
    invoice.save()

    payment_line_items: List[PaymentLineItemModel] = invoice.payment_line_items
    refund_amount = float(payment_line_items[0].filing_fees / 2)
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": refund_amount,
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/refunds",
        data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == Error.INVALID_REQUEST.name
    assert RefundModel.find_by_invoice_id(inv_id) is None

    refunds_partial: List[RefundPartialModel] = RefundService.get_refund_partials_by_invoice_id(inv_id)
    assert not refunds_partial
    assert len(refunds_partial) == 0


def test_refund_validation_for_disbursements(session, client, jwt, app, monkeypatch):
    """Assert that the partial refund amount validation returns 400 when the invoice corp_type has disbursements."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inv_id = rv.json.get("id")
    invoice: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.corp_type_code = "VS"
    invoice.save()

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_line_items: List[PaymentLineItemModel] = invoice.payment_line_items
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": float(payment_line_items[0].filing_fees),
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/refunds",
        data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == Error.PARTIAL_REFUND_DISBURSEMENTS_UNSUPPORTED.name
    assert RefundModel.find_by_invoice_id(inv_id) is None


@pytest.mark.parametrize(
    "fee_type",
    [
        RefundsPartialType.BASE_FEES.value,
        RefundsPartialType.FUTURE_EFFECTIVE_FEES.value,
        RefundsPartialType.PRIORITY_FEES.value,
        RefundsPartialType.SERVICE_FEES.value,
    ],
)
def test_create_refund_validation(session, client, jwt, app, monkeypatch, fee_type):
    """Assert that the partial refund amount validation returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request()),
        headers=headers,
    )
    inv_id = rv.json.get("id")
    invoice: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.save()

    data = {
        "clientSystemUrl": "http://localhost:8080/coops-web/transactions/transaction_id=abcd",
        "payReturnUrl": "http://localhost:8080/pay-web",
    }
    receipt_number = "123451"
    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/transactions",
        data=json.dumps(data),
        headers=headers,
    )
    txn_id = rv.json.get("id")
    client.patch(
        f"/api/v1/payment-requests/{inv_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_line_items: List[PaymentLineItemModel] = invoice.payment_line_items
    payment_line_item = payment_line_items[0]
    refund_amount = 0
    match fee_type:
        case RefundsPartialType.BASE_FEES.value:
            refund_amount = payment_line_item.filing_fees + 1
        case RefundsPartialType.FUTURE_EFFECTIVE_FEES.value:
            refund_amount = payment_line_item.future_effective_fees + 1
        case RefundsPartialType.SERVICE_FEES.value:
            refund_amount = payment_line_item.service_fees + 1
        case RefundsPartialType.PRIORITY_FEES.value:
            refund_amount = payment_line_item.priority_fees + 1
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": float(refund_amount),
            "refundType": fee_type,
        }
    ]
    base_paybc_response = _get_base_paybc_response()
    with patch("pay_api.services.direct_pay_service.DirectPayService.get") as mock_get:
        mock_get.return_value.ok = True
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = base_paybc_response

        rv = client.post(
            f"/api/v1/payment-requests/{inv_id}/refunds",
            data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
            headers=headers,
        )
        assert rv.status_code == 400
        assert rv.json.get("type") == Error.REFUND_AMOUNT_INVALID.name
        assert RefundModel.find_by_invoice_id(inv_id) is None


def _get_base_paybc_response():
    return {
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
                "revenueaccount": "None.None.None.None.None.000000.0000",
                "revenueamount": "30",
                "glstatus": "CMPLT",
                "glerrormessage": None,
                "refund_data": [
                    {
                        "txn_refund_distribution_id": 103570,
                        "revenue_amount": 30,
                        "refund_date": "2023-04-15T20:13:36Z",
                        "refundglstatus": "CMPLT",
                        "refundglerrormessage": None,
                    }
                ],
            },
            {
                "linenumber": "2",
                "revenueaccount": "None.None.None.None.None.000000.0001",
                "revenueamount": "1.5",
                "glstatus": "CMPLT",
                "glerrormessage": None,
                "refund_data": [
                    {
                        "txn_refund_distribution_id": 103182,
                        "revenue_amount": 1.5,
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
