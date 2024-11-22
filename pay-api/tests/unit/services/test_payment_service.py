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
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, ConnectTimeout, HTTPError

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services import CFSService
from pay_api.services.internal_pay_service import InternalPayService
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.services.payment_service import PaymentService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus, RoutingSlipStatus
from pay_api.utils.errors import Error
from tests.utilities.base_test import (
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
        assert excinfo.type == Exception

    with patch(
        "pay_api.services.direct_pay_service.DirectPayService.create_invoice",
        side_effect=Exception("mocked error"),
    ):
        with pytest.raises(Exception) as excinfo:
            PaymentService.create_invoice(
                get_payment_request_with_payment_method(payment_method=PaymentMethod.DIRECT_PAY.value),
                get_auth_basic_user(),
            )
        assert excinfo.type == Exception


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
    invoice = factory_invoice(payment_account, total=10)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()

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


def test_create_eft_payment_ff_disabled(session, public_user_mock):
    """Assert that the payment method EFT feature flag properly disables record creation."""
    factory_payment_account(payment_method_code=PaymentMethod.EFT.value).save()

    with patch("pay_api.services.payment_service.flags.is_on", return_value=False):
        with pytest.raises(BusinessException) as exception:
            PaymentService.create_invoice(
                get_payment_request_with_service_fees(business_identifier="CP0002000"),
                get_auth_premium_user(),
            )

        assert exception is not None
        assert exception.value.code == Error.INVALID_PAYMENT_METHOD.name


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
