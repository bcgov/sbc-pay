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

"""Tests to assure the Payment Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, ConnectTimeout, HTTPError

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.models import CfsAccount, FeeSchedule, Invoice, Payment, PaymentAccount
from pay_api.models import FeeCode as FeeCodeModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services import CFSService
from pay_api.services.fee_schedule import FeeSchedule as FeeScheduleService
from pay_api.services.internal_pay_service import InternalPayService
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.services.payment_line_item import PaymentLineItem
from pay_api.services.payment_service import PaymentService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus, RoutingSlipStatus
from tests.utilities.base_test import (
    factory_corp_type_model,
    factory_distribution_code,
    factory_distribution_link,
    factory_fee_model,
    factory_fee_schedule_model,
    factory_filing_type_model,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_payment_transaction,
    factory_routing_slip,
    get_auth_basic_user,
    get_auth_premium_user,
    get_auth_staff,
    get_payment_request,
    get_payment_request_with_payment_method,
    get_payment_request_with_service_fees,
    get_routing_slip_payment_request,
    get_zero_dollar_payment_request,
)

test_user_token = {"preferred_username": "test"}


def test_create_payment_record(session, public_user_mock):
    """Assert that the payment records are created."""
    payment_response = PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get("id") is not None
    # Create another payment with same request, the account should be the same
    PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))

    assert account_id == account_model.id


def test_create_payment_record_with_direct_pay(session, public_user_mock):
    """Assert that the payment records are created."""
    payment_response = PaymentService.create_invoice(
        get_payment_request(), get_auth_basic_user(PaymentMethod.DIRECT_PAY.value)
    )
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get("id") is not None
    # Create another payment with same request, the account should be the same
    PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))

    assert account_id == account_model.id


def test_create_payment_record_with_internal_pay(session, public_user_mock):
    """Assert that the payment records are created."""
    # Create invoice without routing slip.
    payment_response = PaymentService.create_invoice(get_routing_slip_payment_request(), get_auth_staff())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_staff().get("account").get("id"))
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get("id") is not None

    rs_number = "123456789"
    rs = factory_routing_slip(number=rs_number, payment_account_id=account_id, remaining_amount=50.00)
    rs.save()

    # Create another invoice with a routing slip.
    PaymentService.create_invoice(get_routing_slip_payment_request(), get_auth_staff())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_staff().get("account").get("id"))

    assert account_id == account_model.id

    rs = RoutingSlipModel.find_by_number(rs_number)
    assert rs.remaining_amount == 0.0
    """12033 - Scenario 1.

    Manual transaction reduces RS to 0.00
    Routing slip status becomes Completed
    """
    assert rs.status == RoutingSlipStatus.COMPLETE.name


def test_create_payment_record_rollback(session, public_user_mock):
    """Assert that the payment records are created."""
    # Mock here that the invoice update fails here to test the rollback scenario
    with patch("pay_api.services.invoice.Invoice.flush", side_effect=Exception("mocked error")):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
        assert excinfo.type is Exception

    with patch(
        "pay_api.services.direct_sale_service.DirectSaleService.create_invoice",
        side_effect=Exception("mocked error"),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_invoice(
                get_payment_request_with_payment_method(payment_method=PaymentMethod.DIRECT_PAY.value),
                get_auth_basic_user(),
            )
        assert excinfo.type is Exception


def test_create_payment_record_rollback_on_paybc_connection_error(session, public_user_mock):
    """Assert that the payment records are not created."""
    # Create a payment account
    factory_payment_account()

    # Mock here that the invoice update fails here to test the rollback scenario
    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectionError("mocked error"),
    ):
        with pytest.raises(ServiceUnavailableException) as excinfo:
            PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
        assert excinfo.type == ServiceUnavailableException

    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectTimeout("mocked error"),
    ):
        with pytest.raises(ServiceUnavailableException) as excinfo:
            PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
        assert excinfo.type == ServiceUnavailableException

    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=HTTPError("mocked error"),
    ) as post_mock:
        post_mock.status_Code = 503
        with pytest.raises(HTTPError) as excinfo:
            PaymentService.create_invoice(get_payment_request(), get_auth_basic_user())
        assert excinfo.type == HTTPError


def test_create_zero_dollar_payment_record(session, public_user_mock):
    """Assert that the payment records are created and completed."""
    payment_response = PaymentService.create_invoice(get_zero_dollar_payment_request(), get_auth_basic_user())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get("id") is not None
    assert payment_response.get("status_code") == "COMPLETED"
    # Create another payment with same request, the account should be the same
    PaymentService.create_invoice(get_zero_dollar_payment_request(), get_auth_basic_user())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))
    assert account_id == account_model.id
    assert payment_response.get("status_code") == "COMPLETED"


def test_create_payment_record_with_rs(session, public_user_mock):
    """Assert that the payment records are created and completed."""
    payment_account = factory_payment_account()
    payment_account.save()
    rs = factory_routing_slip(payment_account_id=payment_account.id, total=1000, remaining_amount=1000)
    rs.save()
    cfs_response = {
        "invoice_number": "abcde",
    }

    request = get_payment_request()
    request["accountInfo"] = {"routingSlip": rs.number}
    with patch.object(CFSService, "create_account_invoice", return_value=cfs_response) as mock_post:
        PaymentService.create_invoice(request, get_auth_basic_user())
        mock_post.assert_called()

    request = get_zero_dollar_payment_request()
    request["accountInfo"] = {"routingSlip": rs.number}
    with patch.object(CFSService, "create_account_invoice", return_value=cfs_response) as mock_post:
        PaymentService.create_invoice(request, get_auth_basic_user())
        mock_post.assert_not_called()


def test_delete_payment(session, auth_mock, public_user_mock):
    """Assert that the payment records are soft deleted."""
    payment_account = factory_payment_account()
    # payment = factory_payment()
    payment_account.save()
    # payment.save()
    cfs_account = CfsAccount.find_by_account_id(payment_account.id)[0]
    invoice = factory_invoice(payment_account, total=10, payment_method_code=PaymentMethod.DRAWDOWN.value)
    invoice.cfs_account_id = cfs_account.id
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice_number="INV-001").save()

    # Create a payment for this reference
    payment = factory_payment(invoice_number=invoice_reference.invoice_number, invoice_amount=10).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    PaymentService.delete_invoice(invoice.id)
    invoice = Invoice.find_by_id(invoice.id)

    payment = Payment.find_by_id(payment.id)

    assert invoice.invoice_status_code == InvoiceStatus.DELETED.value
    assert payment.payment_status_code == PaymentStatus.DELETED.value


def test_delete_completed_payment(session, auth_mock):
    """Assert that the payment records are soft deleted."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()

    payment = factory_payment(
        invoice_number=invoice_reference.invoice_number,
        payment_status_code=PaymentStatus.COMPLETED.value,
    ).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    with pytest.raises(Exception) as excinfo:
        PaymentService.delete_invoice(invoice.id)
    assert excinfo.type == BusinessException


def test_create_bcol_payment(session, public_user_mock):
    """Assert that the payment records are created."""
    payment_response = PaymentService.create_invoice(
        get_payment_request_with_payment_method(payment_method="DRAWDOWN", business_identifier="CP0002000"),
        get_auth_premium_user(),
    )
    assert payment_response is not None
    assert payment_response.get("payment_method") == "DRAWDOWN"
    assert payment_response.get("status_code") == "COMPLETED"


def test_create_payment_record_with_service_charge(session, public_user_mock):
    """Assert that the payment records are created."""
    # Create a payment request for corp type BC
    payment_response = PaymentService.create_invoice(get_payment_request_with_service_fees(), get_auth_basic_user())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_basic_user().get("account").get("id"))
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get("id") is not None
    assert payment_response.get("service_fees") == 1.50


def test_create_pad_payment(session, public_user_mock):
    """Assert that the payment records are created."""
    factory_payment_account(payment_method_code=PaymentMethod.PAD.value).save()

    payment_response = PaymentService.create_invoice(
        get_payment_request_with_service_fees(business_identifier="CP0002000"),
        get_auth_premium_user(),
    )
    assert payment_response is not None
    assert payment_response.get("payment_method") == PaymentMethod.PAD.value
    assert payment_response.get("status_code") == InvoiceStatus.APPROVED.value


def test_create_online_banking_payment(session, public_user_mock):
    """Assert that the payment records are created."""
    factory_payment_account(payment_method_code=PaymentMethod.ONLINE_BANKING.value).save()

    payment_response = PaymentService.create_invoice(
        get_payment_request_with_service_fees(business_identifier="CP0002000"),
        get_auth_premium_user(),
    )
    assert payment_response is not None
    assert payment_response.get("payment_method") == PaymentMethod.ONLINE_BANKING.value
    assert payment_response.get("status_code") == PaymentStatus.CREATED.value


def test_patch_online_banking_payment_to_direct_pay(session, public_user_mock):
    """Assert that the payment records are created."""
    factory_payment_account(payment_method_code=PaymentMethod.ONLINE_BANKING.value).save()

    payment_response = PaymentService.create_invoice(
        get_payment_request_with_service_fees(business_identifier="CP0002000"),
        get_auth_premium_user(),
    )
    assert payment_response is not None
    assert payment_response.get("payment_method") == PaymentMethod.ONLINE_BANKING.value
    assert payment_response.get("status_code") == PaymentStatus.CREATED.value

    invoice_id = payment_response.get("id")

    request = {"paymentInfo": {"methodOfPayment": PaymentMethod.CC.value}}

    invoice_response = PaymentService.update_invoice(invoice_id, request)
    assert invoice_response.get("payment_method") == PaymentMethod.DIRECT_PAY.value


def test_patch_online_banking_payment_to_cc(session, public_user_mock):
    """Assert that the payment records are created."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.ONLINE_BANKING.value).save()
    payment_account.save()
    # payment.save()
    payment_response = PaymentService.create_invoice(
        get_payment_request_with_service_fees(business_identifier="CP0002000"),
        get_auth_premium_user(),
    )
    invoice_id = payment_response.get("id")

    factory_invoice_reference(invoice_id).save()

    request = {"paymentInfo": {"methodOfPayment": PaymentMethod.CC.value}}

    invoice_response = PaymentService.update_invoice(invoice_id, request)
    assert invoice_response.get("payment_method") == PaymentMethod.CC.value


def test_create_eft_payment(session, public_user_mock):
    """Assert that the payment records are created."""
    factory_payment_account(payment_method_code=PaymentMethod.EFT.value).save()

    payment_response = PaymentService.create_invoice(
        get_payment_request_with_service_fees(business_identifier="CP0002000"),
        get_auth_premium_user(),
    )
    assert payment_response is not None
    assert payment_response.get("payment_method") == PaymentMethod.EFT.value
    assert payment_response.get("status_code") == InvoiceStatus.APPROVED.value


def test_internal_rs_back_active(session, public_user_mock):
    """12033 - Scenario 2.

    Routing slip is complete and a transaction is cancelled
    the balance is restored - Should move back to Active
    """
    payment_response = PaymentService.create_invoice(get_routing_slip_payment_request(), get_auth_staff())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_staff().get("account").get("id"))
    account_id = account_model.id
    assert account_id is not None
    assert payment_response.get("id") is not None

    rs_number = "123456789"
    rs = factory_routing_slip(number=rs_number, payment_account_id=account_id, remaining_amount=50.00)
    rs.save()

    # Create another invoice with a routing slip.
    invoice = PaymentService.create_invoice(get_routing_slip_payment_request(), get_auth_staff())
    account_model = PaymentAccount.find_by_auth_account_id(get_auth_staff().get("account").get("id"))

    assert account_id == account_model.id

    rs = RoutingSlipModel.find_by_number(rs_number)
    assert rs.remaining_amount == 0.0
    assert rs.status == RoutingSlipStatus.COMPLETE.name

    invoice = Invoice.find_by_id(invoice["id"])
    payment_account = PaymentAccountService()
    payment_account._dao = account_model  # pylint: disable=protected-access
    InternalPayService().process_cfs_refund(invoice, payment_account, None)

    assert rs.status == RoutingSlipStatus.ACTIVE.name


def test_calculate_gst_invoice_versus_pli(session, public_user_mock):
    """Test the _calculate_gst method with multiple payment line items."""
    corp_type = factory_corp_type_model("TEST", "Test Corp Type")
    filing_type = factory_filing_type_model("TEST", "Test Filing Type")

    fee_configs = [
        # TEST 1 -> 6 are real ESRA scenarios.
        ("TEST1", 25.00, True),  # 25.00 * 1 = 25.00
        ("TEST2", 50.00, True),  # 50.00 * 1 = 50.00
        ("TEST3", 10.00, True),  # 10.00 * 1 = 10.00
        ("TEST4", 75.00, True),  # 75.00 * 1 = 75.00
        ("TEST5", 100.00, True),  # 100.00 * 1 = 100.00
        ("TEST6", 150.00, True),  # 150.00 * 1 = 150.00
        ("TEST7", 43.39, True),  # 43.39 * 3 = 130.17
        ("TEST8", 143.39, True),  # 143.39 * 7 = 1003.73
        ("TEST9", 33.25, True),  # 33.25 * 3 = 99.75
        ("TEST10", 66.50, True),  # 66.50 * 7 = 465.50
        ("TEST11", 100.25, True),  # 100.25 * 2 = 200.50
        ("TEST12", 12.75, True),  # 12.75 * 5 = 63.75
    ]

    fee_codes = [factory_fee_model(code, amount) for code, amount, _ in fee_configs]
    service_fee_codes = [
        factory_fee_model("SFEE1", 1.00),
        factory_fee_model("SFEE2", 1.00),
        factory_fee_model("SFEE3", 1.00),
        factory_fee_model("SFEE4", 1.00),
        factory_fee_model("SFEE5", 1.00),
        factory_fee_model("SFEE6", 1.00),
        factory_fee_model("SFEE7", 1.00),
        factory_fee_model("SFEE8", 1.00),
        factory_fee_model("SFEE9", 1.00),
        factory_fee_model("SFEE10", 1.00),
        factory_fee_model("SFEE11", 1.00),
        factory_fee_model("SFEE12", 1.00),
    ]

    distribution_code = factory_distribution_code("TEST_DIST")
    distribution_code.save()

    fee_schedules = [
        factory_fee_schedule_model(
            filing_type=filing_type,
            corp_type=corp_type,
            fee_code=fee_code,
            service_fee=service_fee,
            gst_added=gst_enabled,
        )
        for fee_code, service_fee, (_, _, gst_enabled) in zip(fee_codes, service_fee_codes, fee_configs, strict=False)
    ]

    for fee_schedule in fee_schedules:
        distribution_link = factory_distribution_link(
            distribution_code.distribution_code_id, fee_schedule.fee_schedule_id
        )
        distribution_link.save()

    fees = [FeeScheduleService() for _ in fee_schedules]
    quantities = [1, 1, 1, 1, 1, 1, 3, 7, 3, 7, 2, 5]
    for fee, schedule, qty in zip(fees, fee_schedules, quantities, strict=False):
        fee._dao = schedule
        fee.quantity = qty  # Set quantity to ensure total includes quantity * fee_amount
        if schedule.service_fee_code:
            service_fee_amount = FeeCodeModel.find_by_code(schedule.service_fee_code).amount
            fee.service_fees = service_fee_amount

    with patch("pay_api.models.tax_rate.TaxRate.get_gst_effective_rate", return_value=Decimal("0.05")):
        # Calculate GST using fee_schedule properties
        invoice_gst_amount = sum(fee.statutory_fees_gst + fee.service_fees_gst for fee in fees)
        # GST calculated on all fees (all now have gst_added=True):
        # (25.00 + 50.00 + 10.00 + 75.00 + 100.00 + 150.00 + 130.16 + 1003.74 + 99.75 + 465.50 + 200.50 + 63.75)
        # * 0.05 = 118.68

        assert invoice_gst_amount == Decimal("119.28")

        payment_account = factory_payment_account()
        payment_account.save()

        invoice = factory_invoice(payment_account)
        invoice.save()

        line_items = [
            PaymentLineItem.create(invoice_id=invoice.id, fee=fee, filing_info={"quantity": qty})
            for fee, qty in zip(fees, quantities, strict=False)
        ]

        # Refresh the invoice to get the updated payment_line_items
        session.refresh(invoice)
        assert len(invoice.payment_line_items) == 12

        # GST rounding happens at individual level (statutory_fees_gst and service_fees_gst separately)
        # NOT after adding them together
        total_li_gst = sum([line_item.statutory_fees_gst + line_item.service_fees_gst for line_item in line_items])
        assert total_li_gst == invoice_gst_amount

        total_service_fees = sum(line_item.service_fees for line_item in line_items)
        assert total_service_fees == Decimal("12.00")

        expected_totals = [
            Decimal("27.30"),  # 25.00 + 1.00 + (25.00 * 0.05) + 0.05 = 27.30
            Decimal("53.55"),  # 50.00 + 1.00 + (50.00 * 0.05) + 0.05 = 53.55
            Decimal("11.55"),  # 10.00 + 1.00 + (10.00 * 0.05) + 0.05 = 11.55
            Decimal("79.80"),  # 75.00 + 1.00 + (75.00 * 0.05) + 0.05 = 79.80
            Decimal("106.05"),  # 100.00 + 1.00 + (100.00 * 0.05) + 0.05 = 106.05
            Decimal("158.55"),  # 150.00 + 1.00 + (150.00 * 0.05) + 0.05 = 158.55
            Decimal("137.73"),  # 130.17 + 1.00 + (130.17 * 0.05) + 0.05 = 137.73
            Decimal("1054.97"),  # 1003.73 + 1.00 + (1003.73 * 0.05) + 0.05 = 1054.97
            Decimal("105.79"),  # 99.75 + 1.00 + (99.75 * 0.05) + 0.05 = 105.79
            Decimal("489.83"),  # 465.50 + 1.00 + (465.50 * 0.05) + 0.05 = 489.83
            Decimal("211.57"),  # 200.50 + 1.00 + (200.50 * 0.05) + 0.05 = 211.57
            Decimal("67.99"),  # 63.75 + 1.00 + (63.75 * 0.05) + 0.05 = 67.99
        ]

        for line_item, expected_total in zip(line_items, expected_totals, strict=False):
            assert (
                line_item.total + line_item.service_fees + line_item.statutory_fees_gst + line_item.service_fees_gst
                == expected_total
            )
