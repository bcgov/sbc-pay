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
from _decimal import Decimal
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import Credit as CreditModel
from pay_api.models import EFTCredit, RefundPartialLine
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentMethod as PaymentMethodModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundsPartial as RefundPartialModel
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.refund import RefundService
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import (
    CfsAccountStatus,
    DisbursementStatus,
    EFTCreditInvoiceStatus,
    EJVLinkType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    RefundsPartialType,
    Role,
    TransactionStatus,
)
from pay_api.utils.errors import Error
from tests.utilities.base_test import (
    factory_eft_credit,
    factory_eft_credit_invoice_link,
    factory_eft_file,
    factory_eft_shortname,
    factory_invoice_reference,
    get_claims,
    get_eft_enable_account_payload,
    get_payment_request,
    get_payment_request_with_payment_method,
    get_unlinked_pad_account_payload,
    token_header,
)


def test_create_refund(session, client, jwt, app, monkeypatch, mocker):
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
    assert rv.status_code == 201
    assert rv.json.get("id") is not None
    txn_id = rv.json.get("id")
    rv = client.patch(
        f"/api/v1/payment-requests/{inv_id}/transactions/{txn_id}",
        data=json.dumps({"receipt_number": receipt_number}),
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("statusCode") == TransactionStatus.COMPLETED.value

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
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

        mock_publish = Mock()
        mocker.patch("pay_api.services.gcp_queue.GcpQueue.publish", mock_publish)

        rv = client.post(
            f"/api/v1/payment-requests/{inv_id}/refunds",
            data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
            headers=headers,
        )
        assert rv.status_code == 202
        assert rv.json.get("message") == REFUND_SUCCESS_MESSAGES["DIRECT_PAY.PAID"]
        assert RefundModel.find_by_invoice_id(inv_id) is not None
        mock_publish.assert_called()

        refunds_partial = RefundService.get_refund_partials_by_invoice_id(inv_id)
        assert refunds_partial
        assert len(refunds_partial) == 1

        refund = refunds_partial[0]
        assert refund.id is not None
        assert refund.payment_line_item_id == payment_line_items[0].id
        assert refund.refund_amount == refund_amount
        assert refund.refund_type == RefundsPartialType.BASE_FEES.value
        assert refund.is_credit is False

        invoice = InvoiceModel.find_by_id(invoice.id)
        assert invoice.invoice_status_code == InvoiceStatus.PAID.value
        assert invoice.refund_date.date() == datetime.now(tz=UTC).date()
        assert invoice.refund == refund_amount


def test_create_pad_partial_refund(session, client, jwt, app, account_admin_mock, monkeypatch):
    """Assert that the endpoint returns 202 and creates a credit on the account for partial refund."""
    # Create a PAD payment_account and cfs_account
    auth_account_id = 123456

    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    client.post(
        "/api/v1/accounts",
        data=json.dumps(get_unlinked_pad_account_payload(account_id=auth_account_id)),
        headers=headers,
    )
    pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_account_id(pay_account.id)[0]
    cfs_account.cfs_party = "2222"
    cfs_account.cfs_account = "2222"
    cfs_account.cfs_site = "2222"
    cfs_account.status = CfsAccountStatus.ACTIVE.value
    cfs_account.save()

    pay_account.pad_activation_date = datetime.now(tz=UTC)
    pay_account.save()

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Account-Id": auth_account_id,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_payment_method(payment_method=PaymentMethod.PAD.value)),
        headers=headers,
    )

    inv_id = rv.json.get("id")

    inv: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    inv.invoice_status_code = InvoiceStatus.PAID.value
    inv.payment_date = datetime.now(tz=UTC)
    inv.cfs_account_id = cfs_account.id
    inv.save()

    corp_type = CorpTypeModel.find_by_code(inv.corp_type_code)
    corp_type.has_partner_disbursements = True
    corp_type.save()

    payment_line_items: list[PaymentLineItemModel] = inv.payment_line_items

    refund_amount = float(payment_line_items[0].filing_fees / 2)
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": refund_amount,
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    with patch("pay_api.services.cfs_service.CFSService.create_cms") as mock_create_cms:
        mock_create_cms.return_value = {"credit_memo_number": "CM-123456"}

        token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
        headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
        rv = client.post(
            f"/api/v1/payment-requests/{inv_id}/refunds",
            data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
            headers=headers,
        )

        assert rv.status_code == 202
        assert rv.json.get("message") == REFUND_SUCCESS_MESSAGES["PAD.PAID"]

        assert RefundModel.find_by_invoice_id(inv_id) is not None

        refunds_partial = RefundService.get_refund_partials_by_invoice_id(inv_id)
        assert refunds_partial
        assert len(refunds_partial) == 1

        refund = refunds_partial[0]
        assert refund.id is not None
        assert refund.payment_line_item_id == payment_line_items[0].id
        assert refund.refund_amount == refund_amount
        assert refund.refund_type == RefundsPartialType.BASE_FEES.value
        assert refund.is_credit is True

        inv = InvoiceModel.find_by_id(inv.id)
        assert inv.invoice_status_code == InvoiceStatus.PAID.value
        assert inv.refund_date.date() == datetime.now(tz=UTC).date()
        assert inv.refund == refund_amount

        credit = CreditModel.query.filter_by(account_id=inv.payment_account_id).first()
        assert credit is not None
        assert credit.amount == Decimal(str(refund_amount))
        assert credit.remaining_amount == Decimal(str(refund_amount))
        assert credit.is_credit_memo is True

        pay_account = PaymentAccountModel.find_by_id(inv.payment_account_id)
        assert pay_account.pad_credit == Decimal(str(refund_amount))

        partial_refund = refunds_partial[0]
        disbursements = PartnerDisbursementsModel.query.filter_by(
            target_id=partial_refund.id, target_type=EJVLinkType.PARTIAL_REFUND.value
        ).all()

        assert len(disbursements) == 1
        assert disbursements[0].amount == partial_refund.refund_amount
        assert disbursements[0].is_reversal is True
        assert disbursements[0].partner_code == inv.corp_type_code
        assert disbursements[0].status_code == DisbursementStatus.WAITING_FOR_JOB.value


def test_create_partial_refund_fails(session, client, jwt, app, monkeypatch):
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

    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
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
    assert rv.json.get("type") == Error.PARTIAL_REFUND_INVOICE_NOT_PAID.name
    assert RefundModel.find_by_invoice_id(inv_id) is None

    refunds_partial = RefundService.get_refund_partials_by_invoice_id(inv_id)
    assert not refunds_partial
    assert len(refunds_partial) == 0


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

    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
    payment_line_item = payment_line_items[0]
    refund_amount = 0
    match fee_type:
        case RefundsPartialType.BASE_FEES.value:
            refund_amount = payment_line_item.filing_fees + 1
        case RefundsPartialType.FUTURE_EFFECTIVE_FEES.value:
            refund_amount = payment_line_item.future_effective_fees + 1
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
        error_name = Error.REFUND_AMOUNT_INVALID.name

        if fee_type == RefundsPartialType.SERVICE_FEES.value:
            error_name = Error.PARTIAL_REFUND_SERVICE_FEES_NOT_ALLOWED.name

        assert rv.status_code == 400
        assert rv.json.get("type") == error_name
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


def test_invalid_payment_method_partial_refund(session, client, jwt, app, monkeypatch):
    """Assert that the partial refund unsupported payment method returns 400."""
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
    invoice.payment_method_code = PaymentMethod.EFT.value
    invoice.save()
    set_payment_method_partial_refund(invoice.payment_method_code, False)

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": float(1),
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/refunds",
        data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
        headers=headers,
    )

    assert rv.status_code == 400
    assert rv.json.get("type") == Error.PARTIAL_REFUND_PAYMENT_METHOD_UNSUPPORTED.name
    assert RefundModel.find_by_invoice_id(inv_id) is None
    assert not RefundPartialModel.get_partial_refunds_for_invoice(inv_id)


def setup_cfs_account(jwt, client, auth_account_id, account_payload):
    """Create cfs account."""
    token = jwt.create_jwt(get_claims(role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    client.post(
        "/api/v1/accounts",
        data=json.dumps(account_payload),
        headers=headers,
    )
    pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_account_id(pay_account.id)[0]
    cfs_account.cfs_party = "2222"
    cfs_account.cfs_account = "2222"
    cfs_account.cfs_site = "2222"
    cfs_account.status = CfsAccountStatus.ACTIVE.value
    cfs_account.save()

    return cfs_account


def test_eft_partial_refund_validation(session, client, jwt, app, monkeypatch):
    """Assert that the partial refund validation errors return 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    auth_account_id = 4567
    cfs_account = setup_cfs_account(
        jwt=jwt,
        client=client,
        auth_account_id=auth_account_id,
        account_payload=get_eft_enable_account_payload(
            payment_method=PaymentMethod.EFT.value, account_id=auth_account_id
        ),
    )
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_payment_method(payment_method=PaymentMethod.EFT.value)),
        headers=headers,
    )

    inv_id = rv.json.get("id")
    invoice: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_method_code = PaymentMethod.EFT.value
    invoice.payment_date = datetime.now(tz=UTC)
    invoice.cfs_account_id = cfs_account.id
    invoice.save()
    set_payment_method_partial_refund(invoice.payment_method_code, True)

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": float(1),
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/refunds",
        data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == Error.EFT_PARTIAL_REFUND.name

    factory_invoice_reference(
        invoice_id=invoice.id, invoice_number="1234", status_code=InvoiceReferenceStatus.COMPLETED.value
    ).save()

    rv = client.post(
        f"/api/v1/payment-requests/{inv_id}/refunds",
        data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
        headers=headers,
    )
    assert rv.status_code == 400
    assert rv.json.get("type") == Error.EFT_PARTIAL_REFUND_MISSING_LINKS.name


def test_eft_partial_refund(session, client, jwt, app, monkeypatch):
    """Assert that the partial refund for EFT works."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    auth_account_id = 4567
    cfs_account = setup_cfs_account(
        jwt=jwt,
        client=client,
        auth_account_id=auth_account_id,
        account_payload=get_eft_enable_account_payload(
            payment_method=PaymentMethod.EFT.value, account_id=auth_account_id
        ),
    )
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request_with_payment_method(payment_method=PaymentMethod.EFT.value)),
        headers=headers,
    )

    inv_id = rv.json.get("id")
    invoice: InvoiceModel = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_method_code = PaymentMethod.EFT.value
    invoice.payment_date = datetime.now(tz=UTC)
    invoice.cfs_account_id = cfs_account.id
    invoice.save()
    corp_type = CorpTypeModel.find_by_code(invoice.corp_type_code)
    corp_type.has_partner_disbursements = True
    corp_type.save()

    factory_invoice_reference(
        invoice_id=invoice.id, invoice_number="1234", status_code=InvoiceReferenceStatus.COMPLETED.value
    ).save()

    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()
    eft_file = factory_eft_file()
    eft_credit = factory_eft_credit(
        eft_file_id=eft_file.id, short_name_id=short_name.id, amount=invoice.total, remaining_amount=0
    )
    factory_eft_credit_invoice_link(
        invoice_id=invoice.id,
        eft_credit_id=eft_credit.id,
        status_code=EFTCreditInvoiceStatus.COMPLETED.value,
        amount=invoice.total,
        link_group_id=2,
    ).save()

    set_payment_method_partial_refund(invoice.payment_method_code, True)

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    refund_amount = float(15)
    payment_line_items: list[PaymentLineItemModel] = invoice.payment_line_items
    refund_revenue = [
        {
            "paymentLineItemId": payment_line_items[0].id,
            "refundAmount": refund_amount,
            "refundType": RefundsPartialType.BASE_FEES.value,
        }
    ]

    with patch("pay_api.services.cfs_service.CFSService.create_cms") as mock_create_cms:
        mock_create_cms.return_value = {"credit_memo_number": "CM-123456"}
        rv = client.post(
            f"/api/v1/payment-requests/{inv_id}/refunds",
            data=json.dumps({"reason": "Test", "refundRevenue": refund_revenue}),
            headers=headers,
        )

        assert rv.status_code == 202
        assert rv.json.get("message") == REFUND_SUCCESS_MESSAGES["EFT.PAID"]
        assert RefundModel.find_by_invoice_id(inv_id) is not None

    refunds_partial = RefundService.get_refund_partials_by_invoice_id(inv_id)
    assert refunds_partial
    assert len(refunds_partial) == 1

    refund = refunds_partial[0]
    assert refund.id is not None
    assert refund.payment_line_item_id == payment_line_items[0].id
    assert refund.refund_amount == refund_amount
    assert refund.refund_type == RefundsPartialType.BASE_FEES.value
    assert refund.is_credit is True

    inv = InvoiceModel.find_by_id(inv_id)
    assert inv.invoice_status_code == InvoiceStatus.PAID.value
    assert inv.refund_date.date() == datetime.now(tz=UTC).date()
    assert inv.refund == refund_amount

    credit = CreditModel.query.filter_by(account_id=inv.payment_account_id).first()
    assert credit is not None
    assert credit.amount == Decimal(str(refund_amount))
    assert credit.remaining_amount == Decimal(str(refund_amount))
    assert credit.is_credit_memo is True

    eft_credits = EFTCredit.get_eft_credits(short_name.id)
    assert eft_credits
    assert len(eft_credits) == 1
    assert eft_credits[0].amount == invoice.total
    assert eft_credits[0].remaining_amount == Decimal(str(refund_amount))

    partial_refund = refunds_partial[0]
    disbursements = PartnerDisbursementsModel.query.filter_by(
        target_id=partial_refund.id, target_type=EJVLinkType.PARTIAL_REFUND.value
    ).all()

    assert len(disbursements) == 1
    assert disbursements[0].amount == partial_refund.refund_amount
    assert disbursements[0].is_reversal is True
    assert disbursements[0].partner_code == inv.corp_type_code
    assert disbursements[0].status_code == DisbursementStatus.WAITING_FOR_JOB.value

    pay_account = PaymentAccountModel.find_by_id(invoice.payment_account_id)
    assert pay_account.eft_credit == refund_amount
    assert pay_account.ob_credit is None
    assert pay_account.pad_credit is None


def set_payment_method_partial_refund(payment_method_code: str, enabled: bool):
    """Set partial refund flag on payment method."""
    payment_method = PaymentMethodModel.find_by_code(payment_method_code)
    payment_method.partial_refund = enabled
    payment_method.save()
