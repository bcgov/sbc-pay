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

"""Tests to assure the Refund Service.

Test-Suite to ensure that the Refund Service is working as expected.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models.cfs_account import CfsAccount
from pay_api.services import RefundService
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import (
    EFTCreditInvoiceStatus,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    TransactionStatus,
)
from pay_api.utils.user_context import UserContext
from tests.utilities.base_test import (
    factory_eft_credit,
    factory_eft_credit_invoice_link,
    factory_eft_file,
    factory_eft_shortname,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_transaction,
    factory_receipt,
)


def test_create_refund_for_unpaid_invoice(session):
    """Assert that the create refund fails for unpaid invoices."""
    payment_account = factory_payment_account()
    payment_account.save()

    i = factory_invoice(payment_account=payment_account)
    i.save()
    factory_invoice_reference(i.id).save()

    with pytest.raises(Exception) as excinfo:
        RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"}, products=None)
    assert excinfo.type == BusinessException


@pytest.mark.parametrize(
    "payment_method, invoice_status, pay_status, has_reference, expected_inv_status",
    [
        (
            PaymentMethod.PAD.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.CREDITED.value,
        ),
        (
            PaymentMethod.PAD.value,
            InvoiceStatus.APPROVED.value,
            None,
            False,
            InvoiceStatus.CANCELLED.value,
        ),
        (
            PaymentMethod.ONLINE_BANKING.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.CREDITED.value,
        ),
        (
            PaymentMethod.DRAWDOWN.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.REFUND_REQUESTED.value,
        ),
        (
            PaymentMethod.DIRECT_PAY.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.REFUND_REQUESTED.value,
        ),
    ],
)
def test_create_refund_for_paid_invoice(
    session,
    monkeypatch,
    payment_method,
    invoice_status,
    pay_status,
    has_reference,
    expected_inv_status,
    account_admin_mock,
    mocker,
):
    """Assert that the create refund succeeds for paid invoices."""
    expected = REFUND_SUCCESS_MESSAGES[f"{payment_method}.{invoice_status}"]

    if payment_method in [PaymentMethod.PAD.value, PaymentMethod.ONLINE_BANKING.value, PaymentMethod.CC.value]:
        send_email_mock = mocker.patch("pay_api.services.base_payment_system.send_email")

    payment_account = factory_payment_account(payment_method_code=payment_method)
    payment_account.auth_account_id = "test_account_123"
    payment_account.name = "Test Account"
    payment_account.branch_name = "Test Account Branch"
    payment_account.save()

    cfs_account = CfsAccount.find_latest_account_by_account_id(payment_account.id)

    i = factory_invoice(
        payment_account=payment_account, payment_method_code=payment_method, cfs_account_id=cfs_account.id
    )
    i.save()
    if has_reference:
        inv_ref = factory_invoice_reference(i.id)
        inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
        inv_ref.save()

        payment = factory_payment(invoice_number=inv_ref.invoice_number, payment_status_code=pay_status).save()

        factory_payment_transaction(payment_id=payment.id, status_code=TransactionStatus.COMPLETED.value).save()

    i.invoice_status_code = invoice_status
    i.save()

    factory_receipt(invoice_id=i.id, receipt_number="1234569546456").save()
    mock_publish = Mock()
    mocker.patch("pay_api.services.gcp_queue.GcpQueue.publish", mock_publish)
    message = RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"}, products=None)
    i = InvoiceModel.find_by_id(i.id)

    assert i.invoice_status_code == expected_inv_status
    assert message["message"] == expected
    if i.invoice_status_code in (
        InvoiceStatus.CANCELLED.value,
        InvoiceStatus.CREDITED.value,
        InvoiceStatus.REFUNDED.value,
    ):
        assert i.refund_date
        mock_publish.assert_called()

        if i.invoice_status_code == InvoiceStatus.CREDITED.value and payment_method in [
            PaymentMethod.PAD.value,
            PaymentMethod.ONLINE_BANKING.value,
            PaymentMethod.CC.value,
        ]:
            send_email_mock.assert_called_once()
            recipients_arg = send_email_mock.call_args[0][0]
            assert "admin@example.com" in recipients_arg
            subject_arg = send_email_mock.call_args[0][1]
            assert "credit was added to your account" in subject_arg
            html_body_arg = send_email_mock.call_args[0][2]
            assert "test_account_123" in html_body_arg
            assert "Test Account Branch" in html_body_arg


def test_create_duplicate_refund_for_paid_invoice(session, monkeypatch):
    """Assert that the create duplicate refund fails for paid invoices."""
    payment_account = factory_payment_account()
    payment_account.save()

    i = factory_invoice(payment_account=payment_account)
    i.save()
    inv_ref = factory_invoice_reference(i.id)
    inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
    inv_ref.save()

    payment = factory_payment(invoice_number=inv_ref.invoice_number).save()

    factory_payment_transaction(payment_id=payment.id, status_code=TransactionStatus.COMPLETED.value).save()

    i.invoice_status_code = InvoiceStatus.PAID.value
    i.payment_date = datetime.now(tz=UTC)
    i.save()

    factory_receipt(invoice_id=i.id, receipt_number="953959345343").save()

    RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"}, products=None)
    i = InvoiceModel.find_by_id(i.id)
    payment: PaymentModel = PaymentModel.find_by_id(payment.id)

    assert i.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

    with pytest.raises(Exception) as excinfo:
        RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"}, products=None)
    assert excinfo.type == BusinessException


@pytest.mark.parametrize(
    "test_name, cil_status, inv_status, inv_ref_status, result_cil_status, result_inv_status, result_inv_ref_status",
    [
        (
            "full-refund-paid-cil-completed",
            EFTCreditInvoiceStatus.COMPLETED.value,
            InvoiceStatus.PAID.value,
            InvoiceReferenceStatus.COMPLETED.value,
            EFTCreditInvoiceStatus.PENDING_REFUND.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceReferenceStatus.COMPLETED.value,
        ),
        (
            "full-refund-unpaid-pending-cil-payment",
            EFTCreditInvoiceStatus.PENDING.value,
            InvoiceStatus.APPROVED.value,
            InvoiceReferenceStatus.ACTIVE.value,
            EFTCreditInvoiceStatus.CANCELLED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceReferenceStatus.ACTIVE.value,
        ),
        (
            "full-refund-unpaid-no-cil",
            None,
            InvoiceStatus.APPROVED.value,
            InvoiceReferenceStatus.ACTIVE.value,
            None,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceReferenceStatus.ACTIVE.value,
        ),
    ],
)
def test_create_eft_refund(
    session,
    monkeypatch,
    test_name,
    cil_status,
    inv_status,
    inv_ref_status,
    result_cil_status,
    result_inv_status,
    result_inv_ref_status,
):
    """Assert valid states for EFT refund."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    cfs_account = CfsAccount.find_latest_account_by_account_id(payment_account.id)
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()
    eft_file = factory_eft_file()

    inv_ref = None
    invoice_number = "1234"

    invoice = factory_invoice(
        payment_account=payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=inv_status,
        cfs_account_id=cfs_account.id,
        payment_date=datetime.now(tz=UTC) if inv_status == InvoiceStatus.PAID.value else None,
    ).save()

    eft_credit = factory_eft_credit(
        eft_file_id=eft_file.id, short_name_id=short_name.id, amount=invoice.total, remaining_amount=0
    )

    if cil_status:
        factory_eft_credit_invoice_link(
            invoice_id=invoice.id,
            eft_credit_id=eft_credit.id,
            status_code=cil_status,
            amount=invoice.total,
            link_group_id=2,
        ).save()

    if inv_ref_status:
        inv_ref = factory_invoice_reference(
            invoice_id=invoice.id, invoice_number=invoice_number, status_code=inv_ref_status
        ).save()

    RefundService.create_refund(invoice_id=invoice.id, request={"reason": "Test"}, products=None)
    invoice = InvoiceModel.find_by_id(invoice.id)
    cils = EFTCreditInvoiceModel.find_by_invoice_id(invoice.id)

    assert not cils if result_cil_status is None else cils
    if cils:
        latest_cil = cils[0]
        assert latest_cil.status_code == result_cil_status
    assert invoice.invoice_status_code == result_inv_status
    assert inv_ref.status_code == result_inv_ref_status


@pytest.mark.parametrize(
    "is_system,has_original_username_header,original_username_value,expected_requested_by",
    [
        (True, True, "original_user@domain", "original_user@domain"),
        (True, False, None, "SYSTEM_USER"),
        (False, True, "original_user@domain", "REGULAR_USER"),
        (False, False, None, "REGULAR_USER"),
    ],
)
def test_initialize_refund_requested_by(
    session, is_system, has_original_username_header, original_username_value, expected_requested_by
):
    """Test that _initialize_refund sets requested_by correctly for SYSTEM vs non-SYSTEM users."""

    def mock_token_info():
        return {
            "preferred_username": "system_user" if is_system else "regular_user",
            "realm_access": {"roles": ["system"] if is_system else ["user"]},
            "sub": "test-sub",
            "loginSource": "test",
            "name": "Test User",
            "product_code": "test",
        }

    headers = {}
    if has_original_username_header and original_username_value:
        headers["Original-Username"] = original_username_value

    with patch("pay_api.utils.user_context._get_token_info", mock_token_info):
        with patch("pay_api.utils.user_context.request") as mock_request:
            mock_request.headers = headers
            mock_user = UserContext()

            with patch("pay_api.services.refund.RefundModel") as mock_refund_model:
                mock_refund_instance = mock_refund_model.return_value
                mock_refund_instance.flush = lambda: None

                result = RefundService._initialize_refund(  # pylint: disable=protected-access
                    invoice_id=123, request={"reason": "Test refund"}, user=mock_user
                )

                assert result.requested_by == expected_requested_by
