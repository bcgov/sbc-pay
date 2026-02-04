# Copyright © 2022 Province of British Columbia
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

"""Tests to assure the Direct Sale Service."""

import urllib.parse
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import current_app
from requests.exceptions import HTTPError

from pay_api.exceptions import BusinessException
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule
from pay_api.models.refunds_partial import RefundPartialLine
from pay_api.services.direct_sale_service import DECIMAL_PRECISION, PAYBC_DATE_FORMAT, DirectSaleService, OrderStatus
from pay_api.services.distribution_code import DistributionCode
from pay_api.services.hashing import HashingService
from pay_api.utils.converter import Converter
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, RefundsPartialType
from pay_api.utils.errors import Error
from pay_api.utils.util import current_local_time, generate_transaction_number
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_receipt,
    get_distribution_code_payload,
)


def test_get_payment_system_url(session, public_user_mock):
    """Assert that the url returned is correct."""
    today = current_local_time().strftime(PAYBC_DATE_FORMAT)
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_ref = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    # update the existing gl code with new values
    distribution_code_svc.save_or_update(distribution_code_payload, distribution_code.distribution_code_id)
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    direct_pay_service = DirectSaleService()
    payment_response_url = direct_pay_service.get_payment_system_url_for_invoice(invoice, invoice_ref, "google.com")
    url_param_dict = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(payment_response_url).query))
    assert url_param_dict["trnDate"] == today
    assert url_param_dict["glDate"] == today
    assert url_param_dict["description"] == "Direct_Sale"
    assert url_param_dict["pbcRefNumber"] == current_app.config.get("PAYBC_DIRECT_PAY_REF_NUMBER")
    assert url_param_dict["trnNumber"] == generate_transaction_number(invoice.id)
    assert url_param_dict["trnAmount"] == str(invoice.total)
    assert url_param_dict["paymentMethod"] == "CC"
    assert url_param_dict["redirectUri"] == "google.com"
    revenue_str = (
        f"1:{distribution_code_payload['client']}."
        f"{distribution_code_payload['responsibilityCentre']}."
        f"{distribution_code_payload['serviceLine']}."
        f"{distribution_code_payload['stob']}."
        f"{distribution_code_payload['projectCode']}."
        f"000000.0000:10.00"
    )
    assert url_param_dict["revenue"] == revenue_str
    urlstring = (
        f"trnDate={today}&pbcRefNumber={current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')}&"
        f"glDate={today}&description=Direct_Sale&"
        f"trnNumber={generate_transaction_number(invoice.id)}&"
        f"trnAmount={invoice.total}&"
        f"paymentMethod=CC&"
        f"redirectUri=google.com&"
        f"currency=CAD&"
        f"revenue={revenue_str}"
    )
    expected_hash_str = HashingService.encode(urlstring)
    assert expected_hash_str == url_param_dict["hashValue"]


@pytest.mark.parametrize(
    "base_fee, service_fee, expected_revenue_strs", [(None, 100, 2), (Decimal("0.00"), Decimal("1.50"), 1)]
)
def test_get_payment_system_url_service_fees(session, public_user_mock, base_fee, service_fee, expected_revenue_strs):
    """Assert that the url returned is correct."""
    today = current_local_time().strftime(PAYBC_DATE_FORMAT)
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_ref = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)

    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    # Set service fee distribution
    distribution_code_payload.update({"serviceFeeDistributionCodeId": distribution_code.distribution_code_id})
    # update the existing gl code with new values
    distribution_code_svc.save_or_update(distribution_code_payload, distribution_code.distribution_code_id)

    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        total=base_fee if base_fee is not None else Decimal("10.00"),
        filing_fees=base_fee if base_fee is not None else Decimal("10.00"),
        service_fees=service_fee,
    )
    line.save()
    direct_pay_service = DirectSaleService()
    payment_response_url = direct_pay_service.get_payment_system_url_for_invoice(invoice, invoice_ref, "google.com")
    url_param_dict = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(payment_response_url).query))

    assert url_param_dict["trnDate"] == today
    assert url_param_dict["glDate"] == today
    assert url_param_dict["description"] == "Direct_Sale"
    assert url_param_dict["pbcRefNumber"] == current_app.config.get("PAYBC_DIRECT_PAY_REF_NUMBER")
    assert url_param_dict["trnNumber"] == generate_transaction_number(invoice.id)
    assert url_param_dict["trnAmount"] == str(invoice.total)
    assert url_param_dict["paymentMethod"] == "CC"
    assert url_param_dict["redirectUri"] == "google.com"

    # Generate revenue strings based on base fee and service fee
    revenue_strs = []
    if base_fee is None or base_fee > 0:
        revenue_str = (
            f"1:{distribution_code_payload['client']}."
            f"{distribution_code_payload['responsibilityCentre']}."
            f"{distribution_code_payload['serviceLine']}."
            f"{distribution_code_payload['stob']}."
            f"{distribution_code_payload['projectCode']}."
            f"000000.0000:10.00"
        )
        revenue_strs.append(revenue_str)

    revenue_str_service_fee = (
        f"{len(revenue_strs) + 1}:{distribution_code_payload['client']}."
        f"{distribution_code_payload['responsibilityCentre']}."
        f"{distribution_code_payload['serviceLine']}."
        f"{distribution_code_payload['stob']}."
        f"{distribution_code_payload['projectCode']}."
        f"000000.0000:{format(service_fee, DECIMAL_PRECISION)}"
    )
    revenue_strs.append(revenue_str_service_fee)

    assert url_param_dict["revenue"] == "|".join(revenue_strs)
    assert len(url_param_dict["revenue"].split("|")) == expected_revenue_strs

    urlstring = (
        f"trnDate={today}&pbcRefNumber={current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')}&"
        f"glDate={today}&description=Direct_Sale&"
        f"trnNumber={generate_transaction_number(invoice.id)}&"
        f"trnAmount={invoice.total}&"
        f"paymentMethod=CC&"
        f"redirectUri=google.com&"
        f"currency=CAD&"
        f"revenue={url_param_dict['revenue']}"
    )
    expected_hash_str = HashingService.encode(urlstring)
    assert expected_hash_str == url_param_dict["hashValue"]


def test_create_revenue_string_single_line_item(session, public_user_mock):
    """Test _create_revenue_string with single payment line item."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account)
    invoice.save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")

    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        total=Decimal("100.00"),
        service_fees=Decimal("0"),
        statutory_fees_gst=Decimal("0"),
        service_fees_gst=Decimal("0"),
    )
    line.save()
    result = DirectSaleService._create_revenue_string(invoice)

    assert "1:" in result
    assert ":100.00" in result
    assert "|" not in result


def test_create_revenue_string_with_service_fees(session, public_user_mock):
    """Test _create_revenue_string with service fees included."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account, total=Decimal("125.00"), service_fees=Decimal("25.00"))
    invoice.save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    distribution_code_payload.update({"serviceFeeDistributionCodeId": distribution_code.distribution_code_id})
    distribution_code_svc.save_or_update(distribution_code_payload, distribution_code.distribution_code_id)

    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        total=Decimal("100.00"),
        service_fees=Decimal("25.00"),
        statutory_fees_gst=Decimal("0"),
        service_fees_gst=Decimal("0"),
    )
    line.save()

    result = DirectSaleService._create_revenue_string(invoice)
    lines = result.split("|")

    assert len(lines) == 2
    assert lines[0] == "1:100.22222.20244.9000.1111111.000000.0000:100.00"
    assert lines[1] == "2:100.22222.20244.9000.1111111.000000.0000:25.00"


def test_create_revenue_string_multiple_line_items(session, public_user_mock):
    """Test _create_revenue_string with multiple payment line items."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account, total=Decimal("150.00"))
    invoice.save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    distribution_code_payload.update({"serviceFeeDistributionCodeId": distribution_code.distribution_code_id})
    distribution_code_svc.save_or_update(distribution_code_payload, distribution_code.distribution_code_id)

    line1 = factory_payment_line_item(
        invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, total=Decimal("100.00"), service_fees=Decimal("0")
    )
    line1.save()
    line2 = factory_payment_line_item(
        invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, total=Decimal("50.00"), service_fees=Decimal("0")
    )
    line2.save()

    result = DirectSaleService._create_revenue_string(invoice)

    lines = result.split("|")
    assert len(lines) == 2
    lines.sort()
    assert ":100.00" in result
    assert ":50.00" in result


def test_create_revenue_string_with_all_fee_types(session, public_user_mock):
    """Test _create_revenue_string with all types of fees."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account, total=Decimal("133.75"))
    invoice.save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    distribution_code_payload.update({"serviceFeeDistributionCodeId": distribution_code.distribution_code_id})
    distribution_code_payload.update({"serviceFeeGstDistributionCodeId": distribution_code.distribution_code_id})
    distribution_code_payload.update({"statutoryFeesGstDistributionCodeId": distribution_code.distribution_code_id})
    distribution_code_svc.save_or_update(distribution_code_payload, distribution_code.distribution_code_id)

    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        total=Decimal("100.00"),
        service_fees=Decimal("25.00"),
        service_fees_gst=Decimal("3.75"),
        statutory_fees_gst=Decimal("5.00"),
    )
    line.save()

    result = DirectSaleService._create_revenue_string(invoice)

    lines = result.split("|")
    assert len(lines) == 4
    assert lines[0] == "1:100.22222.20244.9000.1111111.000000.0000:100.00"
    assert lines[1] == "2:100.22222.20244.9000.1111111.000000.0000:5.00"
    assert lines[2] == "3:100.22222.20244.9000.1111111.000000.0000:25.00"
    assert lines[3] == "4:100.22222.20244.9000.1111111.000000.0000:3.75"


def test_create_revenue_string_with_empty_service_fees(session, public_user_mock):
    """Test _create_revenue_string with empty service fees."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account, total=Decimal("100.00"))
    invoice.save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    distribution_code_payload.update({"serviceFeeDistributionCodeId": distribution_code.distribution_code_id})
    distribution_code_svc.save_or_update(distribution_code_payload, distribution_code.distribution_code_id)

    line = factory_payment_line_item(
        invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, total=Decimal("100.00"), service_fees=Decimal("0")
    )
    line.save()

    line = factory_payment_line_item(
        invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, total=Decimal("0.00"), service_fees=Decimal("0")
    )
    line.fee_distribution_id = None
    line.save()

    result = DirectSaleService._create_revenue_string(invoice)
    lines = result.split("|")
    assert len(lines) == 1
    assert lines[0] == "1:100.22222.20244.9000.1111111.000000.0000:100.00"


def test_get_receipt(session, public_user_mock):
    """Assert that get receipt is working."""
    response_url = (
        "trnApproved=1&messageText=Approved&trnOrderId=1003598&trnAmount=201.00&paymentMethod=CC"
        "&cardType=VI&authCode=TEST&trnDate=2020-08-11&pbcTxnNumber=1"
    )
    invalid_hash = "&hashValue=0f7953db6f02f222f1285e1544c6a765"
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_ref = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    service_fee = 100
    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        service_fees=service_fee,
    )
    line.save()
    direct_pay_service = DirectSaleService()
    rcpt = direct_pay_service.get_receipt(payment_account, f"{response_url}{invalid_hash}", invoice_ref)
    assert rcpt is None

    valid_hash = f"&hashValue={HashingService.encode(response_url)}"
    rcpt = direct_pay_service.get_receipt(payment_account, f"{response_url}{valid_hash}", invoice_ref)
    assert rcpt is not None

    # Test receipt without response_url
    rcpt = direct_pay_service.get_receipt(payment_account, None, invoice_ref)
    assert rcpt is not None


def test_process_cfs_refund_success(session, monkeypatch):
    """Assert refund is successful, when providing a PAID invoice, receipt, a COMPLETED invoice reference."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_date = datetime.now(tz=UTC)
    invoice.save()
    receipt = factory_receipt(invoice.id, invoice.id, receipt_amount=invoice.total).save()
    receipt.save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice.id)
    invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
    invoice_reference.save()

    direct_pay_service = DirectSaleService()

    direct_pay_service.process_cfs_refund(invoice, payment_account, None)
    assert True


def test_process_cfs_refund_duplicate_refund(session, monkeypatch):
    """Assert duplicate refund throws an exception.

    Assert approved = 0, throws an exception.
    """
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_date = datetime.now(tz=UTC)
    invoice.save()
    receipt = factory_receipt(invoice.id, invoice.id, receipt_amount=invoice.total).save()
    receipt.save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice.id)
    invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
    invoice_reference.save()
    direct_pay_service = DirectSaleService()

    with patch("pay_api.services.oauth_service.requests.post") as mock_post:
        mock_post.side_effect = HTTPError()
        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 400
        mock_post.return_value.json.return_value = {
            "message": "Bad Request",
            "errors": ["Duplicate refund - Refund has been already processed"],
        }
        with pytest.raises(BusinessException) as excinfo:
            direct_pay_service.process_cfs_refund(invoice, payment_account, None)
            assert invoice.invoice_status_code == InvoiceStatus.PAID.value

    with patch("pay_api.services.oauth_service.requests.post") as mock_post:
        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "id": "10006713",
            "approved": 0,
            "amount": 101.50,
            "message": "Error?",
            "created": "2022-08-17T11:51:41.000+00:00",
            "orderNumber": "19979",
            "txnNumber": "REGT00005433",
        }
        with pytest.raises(BusinessException) as excinfo:
            direct_pay_service.process_cfs_refund(invoice, payment_account, None)
            assert excinfo.value.code == Error.DIRECT_PAY_INVALID_RESPONSE.name


def test_invoice_status_deserialization():
    """Assert our converter is working for OrderStatus."""
    paybc_response = {
        "revenue": [
            {
                "linenumber": "1",
                "revenueaccount": "112.32363.34725.4375.3200062.000000.0000",
                "revenueamount": "130",
                "glstatus": "CMPLT",
                "glerrormessage": None,
                "refund_data": [],
            },
            {
                "linenumber": "2",
                "revenueaccount": "112.32363.34725.4375.3200054.000000.0000",
                "revenueamount": "1.5",
                "glstatus": "CMPLT",
                "glerrormessage": None,
                "refund_data": [],
                "not_part_of_spec": "heyey",
            },
        ],
        "postedrefundamount": None,
        "refundedamount": None,
        "paymentstatus": None,
    }
    paybc_order_status = Converter().structure(paybc_response, OrderStatus)
    assert paybc_order_status


def _automated_refund_preparation():
    """Help automated_refund tests below."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account, total=30, service_fees=1.5)
    invoice.invoice_status_code = InvoiceStatus.PAID.value
    invoice.payment_date = datetime.now(tz=UTC)
    invoice.save()
    payment_line_item = factory_payment_line_item(invoice.id, fee_schedule_id=1, service_fees=1.5, total=30)
    payment_line_item.save()
    receipt = factory_receipt(invoice.id, invoice.id, receipt_amount=invoice.total).save()
    receipt.save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice.id)
    invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
    invoice_reference.save()
    return invoice, payment_line_item


@pytest.mark.parametrize(
    "test_name, refund_partial",
    [
        (
            "pay_pli_not_exist",
            [
                RefundPartialLine(
                    payment_line_item_id=1,
                    refund_amount=1,
                    refund_type=RefundsPartialType.BASE_FEES.value,
                )
            ],
        ),
        (
            "pay_negative_refund_amount",
            [
                RefundPartialLine(
                    payment_line_item_id=1,
                    refund_amount=-1,
                    refund_type=RefundsPartialType.BASE_FEES.value,
                )
            ],
        ),
        (
            "pay_service_fee_too_high",
            [
                RefundPartialLine(
                    payment_line_item_id=1,
                    refund_amount=3,
                    refund_type=RefundsPartialType.SERVICE_FEES.value,
                )
            ],
        ),
    ],
)
def test_build_automated_refund_payload_validation(session, test_name, refund_partial):
    """Assert validations are working correctly for building refund payload."""
    invoice, payment_line_item = _automated_refund_preparation()
    if test_name == "pay_pli_not_exist":
        refund_partial[0].payment_line_item_id = 999999999
    else:
        refund_partial[0].payment_line_item_id = payment_line_item.id
    direct_pay_service = DirectSaleService()
    with pytest.raises(BusinessException) as excinfo:
        direct_pay_service.build_automated_refund_payload(invoice, refund_partial)
        assert excinfo.value.code == Error.INVALID_REQUEST.name


@pytest.mark.parametrize(
    "test_name, has_exception",
    [
        ("success", False),
        ("paybc_non_match", True),
        ("paybc_amount_too_high", True),
        ("paybc_already_refunded", True),
    ],
)
def test_build_automated_refund_payload_paybc_validation(session, test_name, has_exception):
    """Assert refund payload building works correctly with various PAYBC responses."""
    invoice, payment_line_item = _automated_refund_preparation()
    refund_partial = [
        RefundPartialLine(
            payment_line_item_id=payment_line_item.id,
            refund_amount=Decimal("3.1"),
            refund_type=RefundsPartialType.BASE_FEES.value,
        )
    ]
    direct_pay_service = DirectSaleService()
    base_paybc_response = {
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
    with patch("pay_api.services.direct_pay_service.DirectSaleService.get") as mock_get:
        mock_get.return_value.ok = True
        mock_get.return_value.status_code = 200
        if test_name == "paybc_non_match":
            base_paybc_response["revenue"][0]["revenueaccount"] = "911"
            base_paybc_response["revenue"][1]["revenueaccount"] = "911"
        elif test_name == "paybc_amount_too_high":
            base_paybc_response["revenue"][0]["revenueamount"] = "0.5"
            base_paybc_response["revenue"][1]["revenueamount"] = "0.5"
        elif test_name == "paybc_already_refunded":
            base_paybc_response["refundedamount"] = 31.50
            base_paybc_response["postedrefundamount"] = 31.50
        mock_get.return_value.json.return_value = base_paybc_response
        if has_exception:
            with pytest.raises(BusinessException) as excinfo:
                direct_pay_service.build_automated_refund_payload(invoice, refund_partial)
                assert excinfo.value.code == Error.INVALID_REQUEST.name
        else:
            payload = direct_pay_service.build_automated_refund_payload(invoice, refund_partial)
            assert payload
            assert payload["txnAmount"] == refund_partial[0].refund_amount
            assert payload["refundRevenue"][0]["lineNumber"] == "1"
            assert payload["refundRevenue"][0]["refundAmount"] == refund_partial[0].refund_amount
