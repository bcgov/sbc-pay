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

"""Tests to assure the EFTTask is working correctly.

Test-Suite to ensure that the EFTTask for electronic funds transfer is working as expected.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import CfsAccountStatus, DisbursementStatus
from pay_api.utils.enums import EFTCreditInvoiceStatus as EFTCilStatus
from pay_api.utils.enums import EFTHistoricalTypes
from pay_api.utils.enums import InvoiceReferenceStatus as InvoiceRefStatus
from pay_api.utils.enums import InvoiceStatus, PaymentMethod

from tasks.eft_task import EFTTask

from .factory import (
    factory_create_eft_account,
    factory_create_eft_credit,
    factory_create_eft_credit_invoice_link,
    factory_create_eft_file,
    factory_create_eft_shortname,
    factory_create_eft_shortname_historical,
    factory_create_eft_transaction,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_line_item,
    factory_receipt,
)


def setup_eft_credit_invoice_links_test():
    """Initiate test data."""
    auth_account_id = "1234"
    eft_file = factory_create_eft_file()
    eft_transaction_id = factory_create_eft_transaction(file_id=eft_file.id).id
    short_name_id = factory_create_eft_shortname("heyhey").id
    return auth_account_id, eft_file, short_name_id, eft_transaction_id


tests = [
    (
        "invoice_refund_flow",
        PaymentMethod.EFT.value,
        [InvoiceStatus.REFUND_REQUESTED.value],
        [EFTCilStatus.CANCELLED.value],
        [None],
        0,
        0,
    ),
    (
        "insufficient_amount_on_links",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
        [
            EFTCilStatus.PENDING.value,
            EFTCilStatus.PENDING_REFUND.value,
        ],
        [None],
        0,
        0,
    ),
    (
        "happy_flow_multiple_links",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
        [
            EFTCilStatus.PENDING.value,
            EFTCilStatus.PENDING_REFUND.value,
        ],
        [None, DisbursementStatus.COMPLETED.value],
        2,
        2,
    ),
    (
        "happy_flow",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
        [
            EFTCilStatus.PENDING.value,
            EFTCilStatus.PENDING_REFUND.value,
        ],
        [None, DisbursementStatus.COMPLETED.value],
        2,
        2,
    ),
    (
        "duplicate_active_cfs_account",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
        [
            EFTCilStatus.PENDING.value,
            EFTCilStatus.PENDING_REFUND.value,
        ],
        [None],
        1,
        1,
    ),
    (
        "no_cfs_active",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value],
        [EFTCilStatus.PENDING.value],
        [None],
        0,
        0,
    ),
    (
        "wrong_payment_method",
        PaymentMethod.PAD.value,
        [InvoiceStatus.CREATED.value],
        [EFTCilStatus.PENDING.value],
        [None],
        0,
        0,
    ),
    (
        "credit_invoice_link_status_incorrect",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value],
        [EFTCilStatus.COMPLETED.value, EFTCilStatus.REFUNDED.value],
        [None],
        0,
        0,
    ),
    (
        "wrong_invoice_status",
        PaymentMethod.EFT.value,
        [
            InvoiceStatus.CREDITED.value,
            InvoiceStatus.PARTIAL.value,
            InvoiceStatus.CREATED.value,
        ],
        [EFTCilStatus.PENDING.value],
        [None],
        0,
        0,
    ),
    (
        "no_invoice_reference",
        PaymentMethod.EFT.value,
        [InvoiceStatus.APPROVED.value],
        [EFTCilStatus.PENDING.value],
        [None],
        0,
        0,
    ),
]


@pytest.mark.parametrize(
    "test_name, payment_method, invoice_status_codes, eft_credit_invoice_statuses,"
    + "disbursement_status_codes, pending_count, pending_refund_count",
    tests,
)
def test_eft_credit_invoice_links_by_status(
    session,
    test_name,
    payment_method,
    invoice_status_codes,
    eft_credit_invoice_statuses,
    disbursement_status_codes,
    pending_count,
    pending_refund_count,
):
    """Tests multiple scenarios for EFT credit invoice links."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    max_cfs_account_id = 0
    match test_name:
        case "duplicate_active_cfs_account":
            max_cfs_account_id = (
                CfsAccountModel(
                    status=CfsAccountStatus.ACTIVE.value,
                    account_id=payment_account.id,
                    payment_method=PaymentMethod.EFT.value,
                )
                .save()
                .id
            )
        case "no_cfs_active":
            CfsAccountModel.find_by_account_id(payment_account.id)[0].status = CfsAccountStatus.INACTIVE.value

    eft_credit = factory_create_eft_credit(
        amount=100,
        remaining_amount=0,
        eft_file_id=eft_file.id,
        short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id,
    )

    for invoice_status in invoice_status_codes:
        for disbursement_status in disbursement_status_codes:
            for eft_credit_invoice_status in eft_credit_invoice_statuses:
                invoice = factory_invoice(
                    payment_account=payment_account,
                    payment_method_code=payment_method,
                    status_code=invoice_status,
                    disbursement_status_code=disbursement_status,
                )
                if test_name != "no_invoice_reference":
                    factory_invoice_reference(invoice_id=invoice.id)
                match test_name:
                    case "happy_flow_multiple_links":
                        factory_create_eft_credit_invoice_link(
                            invoice_id=invoice.id,
                            eft_credit_id=eft_credit.id,
                            status_code=eft_credit_invoice_status,
                            amount=invoice.total / 2,
                        )
                        factory_create_eft_credit_invoice_link(
                            invoice_id=invoice.id,
                            eft_credit_id=eft_credit.id,
                            status_code=eft_credit_invoice_status,
                            amount=invoice.total / 2,
                        )
                    case "insufficient_amount_on_links":
                        factory_create_eft_credit_invoice_link(
                            invoice_id=invoice.id,
                            eft_credit_id=eft_credit.id,
                            status_code=eft_credit_invoice_status,
                            amount=invoice.total - 1,
                        )
                    case _:
                        factory_create_eft_credit_invoice_link(
                            invoice_id=invoice.id,
                            eft_credit_id=eft_credit.id,
                            status_code=eft_credit_invoice_status,
                            amount=invoice.total,
                        )

    results = EFTTask.get_eft_credit_invoice_links_by_status(EFTCilStatus.PENDING.value)
    if max_cfs_account_id:
        for invoice, cfs_account, _ in results:
            assert cfs_account.id == max_cfs_account_id
    assert len(results) == pending_count
    results = EFTTask.get_eft_credit_invoice_links_by_status(EFTCilStatus.PENDING_REFUND.value)
    assert len(results) == pending_refund_count
    if test_name == "invoice_refund_flow":
        results = EFTTask.get_eft_credit_invoice_links_by_status(EFTCilStatus.CANCELLED.value)
        assert len(results) == 1


@pytest.mark.parametrize(
    "test_name",
    (
        "happy_path",
        "consolidated_happy",
        "consolidated_mismatch",
        "normal_invoice_missing",
    ),
)
def test_link_electronic_funds_transfers(session, test_name):
    """Test link electronic funds transfers."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(
        payment_account=payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=10,
    )
    invoice_reference = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(
        payment_account_id=payment_account.id,
        payment_method_code=PaymentMethod.EFT.value,
        invoice_amount=351.50,
    )
    eft_credit = factory_create_eft_credit(
        amount=100,
        remaining_amount=0,
        eft_file_id=eft_file.id,
        short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id,
    )
    credit_invoice_link = factory_create_eft_credit_invoice_link(
        invoice_id=invoice.id, eft_credit_id=eft_credit.id, link_group_id=1, amount=5
    )
    credit_invoice_link2 = factory_create_eft_credit_invoice_link(
        invoice_id=invoice.id, eft_credit_id=eft_credit.id, link_group_id=1, amount=5
    )
    eft_historical = factory_create_eft_shortname_historical(
        payment_account_id=payment_account.id,
        short_name_id=short_name_id,
        related_group_link_id=1,
    )
    assert eft_historical.hidden
    assert eft_historical.is_processing

    cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.EFT.value)
    return_value = {}
    original_invoice_reference = None

    match test_name:
        case "consolidated_happy" | "consolidated_mismatch":
            invoice_reference.is_consolidated = True
            invoice_reference.save()
            original_invoice_reference = factory_invoice_reference(
                invoice_id=invoice.id,
                is_consolidated=False,
                status_code=InvoiceRefStatus.CANCELLED.value,
            ).save()
            return_value = {"total": 10.00}
            if test_name == "consolidated_mismatch":
                return_value = {"total": 10.01}
        case "normal_invoice_missing":
            invoice_reference.is_consolidated = True
            invoice_reference.save()
        case _:
            pass

    if test_name in ["consolidated_mismatch", "normal_invoice_missing"]:
        with patch("pay_api.services.CFSService.get_invoice", return_value=return_value) as mock_get_invoice:
            EFTTask.link_electronic_funds_transfers_cfs()
            # No change, the amount didn't match or normal invoice was missing.
            assert invoice_reference.status_code == InvoiceRefStatus.ACTIVE.value
        return

    with patch("pay_api.services.CFSService.reverse_invoice") as mock_reverse_invoice:
        with patch("pay_api.services.CFSService.create_cfs_receipt") as mock_create_receipt:
            with patch("pay_api.services.CFSService.get_invoice", return_value=return_value) as mock_get_invoice:
                EFTTask.link_electronic_funds_transfers_cfs()
                if test_name == "consolidated_happy":
                    mock_reverse_invoice.assert_called()
                    mock_get_invoice.assert_called()
                    mock_create_receipt.assert_called()

    assert cfs_account.status == CfsAccountStatus.ACTIVE.value
    if test_name == "consolidated_happy":
        assert invoice_reference.status_code == InvoiceRefStatus.CANCELLED.value
        assert original_invoice_reference.status_code == InvoiceRefStatus.COMPLETED.value
    else:
        assert invoice_reference.status_code == InvoiceRefStatus.COMPLETED.value
    receipt = ReceiptModel.find_all_receipts_for_invoice(invoice.id)[0]
    assert receipt
    assert receipt.receipt_amount == credit_invoice_link.amount + credit_invoice_link2.amount
    assert receipt.invoice_id == invoice.id
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value
    assert invoice.paid == credit_invoice_link.amount + credit_invoice_link2.amount
    assert invoice.payment_date
    assert credit_invoice_link.status_code == EFTCilStatus.COMPLETED.value
    assert credit_invoice_link2.status_code == EFTCilStatus.COMPLETED.value

    assert not eft_historical.hidden
    assert not eft_historical.is_processing


@pytest.mark.parametrize(
    "test_name, cil_status, inv_status, inv_ref_status, result_cil_status, result_inv_status, result_inv_ref_status",
    [
        (
            "full-refund-cil-paid",
            EFTCilStatus.PENDING_REFUND.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.COMPLETED.value,
            EFTCilStatus.REFUNDED.value,
            InvoiceStatus.REFUNDED.value,
            InvoiceRefStatus.CANCELLED.value,
        ),
        (
            "full-refund-cil-unpaid-cil-cancelled",
            EFTCilStatus.CANCELLED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.ACTIVE.value,
            EFTCilStatus.CANCELLED.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceRefStatus.CANCELLED.value,
        ),
        (
            "reverse-paid-invoice",
            EFTCilStatus.PENDING_REFUND.value,
            InvoiceStatus.PAID.value,
            InvoiceRefStatus.COMPLETED.value,
            EFTCilStatus.REFUNDED.value,
            InvoiceStatus.APPROVED.value,
            InvoiceRefStatus.ACTIVE.value,
        ),
    ],
)
def test_reverse_electronic_funds_transfers(
    session,
    test_name,
    cil_status,
    inv_status,
    inv_ref_status,
    result_cil_status,
    result_inv_status,
    result_inv_ref_status,
):
    """Test reverse electronic funds transfers."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    receipt_number = "1111R"
    invoice_number = "1234"
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)

    invoice = factory_invoice(
        payment_account=payment_account,
        total=30,
        paid=30,
        status_code=inv_status,
        payment_method_code=PaymentMethod.EFT.value,
    )
    invoice.payment_date = datetime.now(tz=timezone.utc)
    invoice.save()

    factory_payment(
        payment_account_id=payment_account.id,
        payment_method_code=PaymentMethod.EFT.value,
        invoice_amount=351.50,
        invoice_number=invoice_number,
    )
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)

    invoice_reference = None
    if inv_ref_status:
        invoice_reference = factory_invoice_reference(
            invoice_id=invoice.id,
            status_code=inv_ref_status,
            invoice_number=invoice_number,
        )
    eft_credit = factory_create_eft_credit(
        amount=100,
        remaining_amount=0,
        eft_file_id=eft_file.id,
        short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id,
    )
    cil = factory_create_eft_credit_invoice_link(
        invoice_id=invoice.id,
        status_code=cil_status,
        eft_credit_id=eft_credit.id,
        amount=30,
    )
    factory_receipt(invoice.id, receipt_number)

    # This record is created through pay-api with the corresponding transaction_type, we are only using
    # STATEMENT_REVERSE since we only want to confirm the job flips the hidden and is_processing flags
    eft_historical = factory_create_eft_shortname_historical(
        payment_account_id=payment_account.id,
        short_name_id=short_name_id,
        related_group_link_id=1,
        transaction_type=EFTHistoricalTypes.STATEMENT_REVERSE.value,
    )
    assert eft_historical.hidden
    assert eft_historical.is_processing

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_reverse:
        with patch("pay_api.services.CFSService.reverse_invoice") as mock_invoice:
            EFTTask.reverse_electronic_funds_transfers_cfs()
            if inv_status == InvoiceStatus.REFUND_REQUESTED.value and invoice_reference:
                mock_invoice.assert_called()
            else:
                mock_invoice.assert_not_called()
            mock_reverse.assert_called()

    assert invoice_reference.status_code == result_inv_ref_status
    assert len(ReceiptModel.find_all_receipts_for_invoice(invoice.id)) == 0
    assert invoice.invoice_status_code == result_inv_status
    assert (
        invoice.paid == 0
        if invoice.invoice_status_code == InvoiceStatus.APPROVED.value
        else invoice.paid == invoice.total
    )
    assert (
        invoice.payment_date is None
        if invoice.invoice_status_code == InvoiceStatus.APPROVED.value
        else invoice.payment_date is not None
    )
    assert invoice.paid == 0 if invoice.invoice_status_code == InvoiceStatus.APPROVED.value else invoice.total
    assert invoice.payment_date is None if invoice.invoice_status_code == InvoiceStatus.APPROVED.value else not None
    assert cil.status_code == result_cil_status
    assert (
        invoice.refund_date is not None
        if result_inv_status in [InvoiceStatus.REFUNDED.value, InvoiceStatus.CANCELLED.value]
        else invoice.refund_date is None
    )
    assert (
        invoice.refund == invoice.total
        if result_inv_status in [InvoiceStatus.REFUNDED.value, InvoiceStatus.CANCELLED.value]
        else invoice.refund is None
    )

    assert not eft_historical.hidden
    assert not eft_historical.is_processing


def test_unlock_overdue_accounts(session):
    """Test unlock overdue account events."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    payment_account.has_overdue_invoices = datetime.now(tz=timezone.utc)
    invoice_1 = factory_invoice(
        payment_account=payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        total=10,
    )
    invoice_1.invoice_status_code = InvoiceStatus.OVERDUE.value
    invoice_1.save()
    factory_invoice_reference(invoice_id=invoice_1.id)
    eft_credit = factory_create_eft_credit(
        amount=100,
        remaining_amount=0,
        eft_file_id=eft_file.id,
        short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id,
    )
    factory_create_eft_credit_invoice_link(invoice_id=invoice_1.id, eft_credit_id=eft_credit.id, amount=10)

    # Create second overdue invoice and confirm unlock is not double called on a payment account
    invoice_2 = factory_invoice(
        payment_account=payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        total=10,
    )
    invoice_2.invoice_status_code = InvoiceStatus.OVERDUE.value
    invoice_2.save()
    factory_invoice_reference(invoice_id=invoice_2.id)
    factory_create_eft_credit_invoice_link(invoice_id=invoice_2.id, eft_credit_id=eft_credit.id, amount=10)

    with patch("pay_api.utils.auth_event.ActivityLogPublisher.publish_unlock_event") as mock_activity_log:
        with patch("pay_api.services.gcp_queue_publisher.publish_to_queue") as mock_gcp_publisher:
            EFTTask.link_electronic_funds_transfers_cfs()
            assert payment_account.has_overdue_invoices is None
            mock_activity_log.assert_called_once()
            call_args = mock_activity_log.call_args[0][0]
            assert call_args.account_id == payment_account.auth_account_id
            assert call_args.current_payment_method == PaymentMethod.EFT.value
            assert call_args.unlock_payment_method == PaymentMethod.EFT.value
            assert call_args.source == "PAY_JOBS"
            mock_gcp_publisher.assert_called()


@pytest.mark.parametrize(
    "test_name, cil_status, inv_status, inv_ref_status, result_cil_status, result_inv_status, result_inv_ref_status",
    [
        (
            "should-skip-with-cil",  # Confirm this is properly skipped for unlinked flow
            EFTCilStatus.PENDING_REFUND.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.ACTIVE.value,
            EFTCilStatus.PENDING_REFUND.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.ACTIVE.value,
        ),
        (
            "should-skip-no-cil-full-refund-paid",  # Paid without EFT credit invoice links, should not refund
            None,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.COMPLETED.value,
            None,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.COMPLETED.value,
        ),
        (
            "full-refund-unpaid",
            None,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceRefStatus.ACTIVE.value,
            None,
            InvoiceStatus.CANCELLED.value,
            InvoiceRefStatus.CANCELLED.value,
        ),
    ],
)
def test_handle_unlinked_refund_requested_invoices(
    session,
    mocker,
    test_name,
    cil_status,
    inv_status,
    inv_ref_status,
    result_cil_status,
    result_inv_status,
    result_inv_ref_status,
):
    """Test reverse electronic funds transfers."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    invoice_number = "1234"
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)

    invoice = factory_invoice(
        payment_account=payment_account,
        total=30,
        paid=30,
        status_code=inv_status,
        payment_method_code=PaymentMethod.EFT.value,
    )
    invoice.payment_date = datetime.now(tz=timezone.utc)
    invoice.save()

    invoice_reference = None
    if inv_ref_status:
        invoice_reference = factory_invoice_reference(
            invoice_id=invoice.id,
            status_code=inv_ref_status,
            invoice_number=invoice_number,
        )
    eft_credit = factory_create_eft_credit(
        amount=100,
        remaining_amount=0,
        eft_file_id=eft_file.id,
        short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id,
    )
    cil = None
    if cil_status:
        cil = factory_create_eft_credit_invoice_link(
            invoice_id=invoice.id,
            status_code=cil_status,
            eft_credit_id=eft_credit.id,
            amount=30,
        )

    mock_publish = Mock()
    mocker.patch("pay_api.services.gcp_queue.GcpQueue.publish", mock_publish)

    with patch("pay_api.services.CFSService.reverse_invoice") as mock_invoice:
        EFTTask.handle_unlinked_refund_requested_invoices()
        if cil_status is None and inv_ref_status == InvoiceRefStatus.ACTIVE.value:
            mock_invoice.assert_called()
            mock_publish.assert_called()
            assert invoice.paid == invoice.total
            assert invoice.payment_date is not None
            assert invoice.paid == invoice.total
            assert invoice.payment_date is not None
            assert invoice_reference.status_code == result_inv_ref_status
            assert invoice.invoice_status_code == result_inv_status
        else:
            mock_invoice.assert_not_called()
            mock_publish.assert_not_called()

        if result_cil_status is not None:
            assert cil.status_code == result_cil_status


def test_rollback_consolidated_invoice():
    """Ensure we can't rollback a consolidated invoice."""
    payment_account = factory_create_eft_account(status=CfsAccountStatus.ACTIVE.value)
    invoice_1 = factory_invoice(payment_account=payment_account).save()
    invoice_reference = factory_invoice_reference(
        invoice_id=invoice_1.id,
        status_code=InvoiceRefStatus.COMPLETED.value,
        is_consolidated=True,
    ).save()
    with pytest.raises(Exception) as excinfo:
        EFTTask._rollback_receipt_and_invoice(
            None,  # pylint: disable=protected-access
            invoice_1,
            None,
            cil_status_code=EFTCilStatus.PENDING_REFUND.value,
        )
        assert "Cannot reverse a consolidated invoice" in excinfo.value.args
    with pytest.raises(Exception) as excinfo:
        EFTTask._handle_invoice_refund(None, invoice_reference)  # pylint: disable=protected-access
        assert "Cannot reverse a consolidated invoice" in excinfo.value.args
