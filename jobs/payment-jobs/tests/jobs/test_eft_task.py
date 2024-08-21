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
from unittest.mock import patch

import pytest

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import (
    CfsAccountStatus, DisbursementStatus, EFTCreditInvoiceStatus, EFTHistoricalTypes, InvoiceReferenceStatus,
    InvoiceStatus, PaymentMethod)

from tasks.eft_task import EFTTask

from .factory import (
    factory_create_eft_account, factory_create_eft_credit, factory_create_eft_credit_invoice_link,
    factory_create_eft_file, factory_create_eft_shortname, factory_create_eft_shortname_historical,
    factory_create_eft_transaction, factory_invoice, factory_invoice_reference, factory_payment,
    factory_payment_line_item, factory_receipt)


def setup_eft_credit_invoice_links_test():
    """Initiate test data."""
    auth_account_id = '1234'
    eft_file = factory_create_eft_file()
    eft_transaction_id = factory_create_eft_transaction(file_id=eft_file.id).id
    short_name_id = factory_create_eft_shortname('heyhey').id
    return auth_account_id, eft_file, short_name_id, eft_transaction_id


tests = [
    ('invoice_refund_flow', PaymentMethod.EFT.value, [InvoiceStatus.REFUND_REQUESTED.value],
     [EFTCreditInvoiceStatus.CANCELLED.value], [None], 0, 0),
    ('insufficient_amount_on_links', PaymentMethod.EFT.value, [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
     [EFTCreditInvoiceStatus.PENDING.value, EFTCreditInvoiceStatus.PENDING_REFUND.value], [None], 0, 0),
    ('happy_flow_multiple_links', PaymentMethod.EFT.value, [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
     [EFTCreditInvoiceStatus.PENDING.value, EFTCreditInvoiceStatus.PENDING_REFUND.value],
        [None, DisbursementStatus.COMPLETED.value], 1, 2),
    ('happy_flow', PaymentMethod.EFT.value, [InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value],
     [EFTCreditInvoiceStatus.PENDING.value,
      EFTCreditInvoiceStatus.PENDING_REFUND.value], [None, DisbursementStatus.COMPLETED.value], 1, 2),
    ('duplicate_active_cfs_account', PaymentMethod.EFT.value, [
     InvoiceStatus.APPROVED.value, InvoiceStatus.PAID.value], [EFTCreditInvoiceStatus.PENDING.value,
                                                               EFTCreditInvoiceStatus.PENDING_REFUND.value],
     [None], 1, 1),
    ('no_cfs_active', PaymentMethod.EFT.value, [
     InvoiceStatus.APPROVED.value], [EFTCreditInvoiceStatus.PENDING.value], [None], 0, 0),
    ('wrong_payment_method', PaymentMethod.PAD.value, [
     InvoiceStatus.CREATED.value], [EFTCreditInvoiceStatus.PENDING.value], [None], 0, 0),
    ('credit_invoice_link_status_incorrect', PaymentMethod.EFT.value, [
     InvoiceStatus.APPROVED.value], [EFTCreditInvoiceStatus.COMPLETED.value, EFTCreditInvoiceStatus.REFUNDED.value],
     [None], 0, 0),
    ('wrong_disbursement', PaymentMethod.EFT.value, [
     InvoiceStatus.APPROVED.value], [EFTCreditInvoiceStatus.PENDING.value], [DisbursementStatus.UPLOADED.value], 0, 0),
    ('wrong_invoice_status', PaymentMethod.EFT.value, [
     InvoiceStatus.CREDITED.value, InvoiceStatus.PARTIAL.value, InvoiceStatus.CREATED.value],
     [EFTCreditInvoiceStatus.PENDING.value], [None], 0, 0),
    ('no_invoice_reference', PaymentMethod.EFT.value, [
         InvoiceStatus.APPROVED.value], [EFTCreditInvoiceStatus.PENDING.value], [None], 0, 0),
]


@pytest.mark.parametrize('test_name, payment_method, invoice_status_codes, eft_credit_invoice_statuses,' +
                         'disbursement_status_codes, pending_count, pending_refund_count', tests)
def test_eft_credit_invoice_links_by_status(session, test_name, payment_method, invoice_status_codes,
                                            eft_credit_invoice_statuses, disbursement_status_codes,
                                            pending_count, pending_refund_count):
    """Tests multiple scenarios for EFT credit invoice links."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    max_cfs_account_id = 0
    match test_name:
        case 'duplicate_active_cfs_account':
            max_cfs_account_id = CfsAccountModel(status=CfsAccountStatus.ACTIVE.value,
                                                 account_id=payment_account.id,
                                                 payment_method=PaymentMethod.EFT.value).save().id
        case 'no_cfs_active':
            CfsAccountModel.find_by_account_id(payment_account.id)[0].status = CfsAccountStatus.INACTIVE.value

    eft_credit = factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id)

    for invoice_status in invoice_status_codes:
        for disbursement_status in disbursement_status_codes:
            for eft_credit_invoice_status in eft_credit_invoice_statuses:
                invoice = factory_invoice(payment_account=payment_account,
                                          payment_method_code=payment_method,
                                          status_code=invoice_status,
                                          disbursement_status_code=disbursement_status)
                if test_name != 'no_invoice_reference':
                    factory_invoice_reference(invoice_id=invoice.id)
                match test_name:
                    case 'happy_flow_multiple_links':
                        factory_create_eft_credit_invoice_link(
                                invoice_id=invoice.id,
                                eft_credit_id=eft_credit.id,
                                status_code=eft_credit_invoice_status,
                                amount=invoice.total / 2)
                        factory_create_eft_credit_invoice_link(
                                invoice_id=invoice.id,
                                eft_credit_id=eft_credit.id,
                                status_code=eft_credit_invoice_status,
                                amount=invoice.total / 2)
                    case 'insufficient_amount_on_links':
                        factory_create_eft_credit_invoice_link(
                                invoice_id=invoice.id,
                                eft_credit_id=eft_credit.id,
                                status_code=eft_credit_invoice_status,
                                amount=invoice.total - 1)
                    case _:
                        factory_create_eft_credit_invoice_link(
                            invoice_id=invoice.id, eft_credit_id=eft_credit.id, status_code=eft_credit_invoice_status,
                            amount=invoice.total)

    results = EFTTask.get_eft_credit_invoice_links_by_status(EFTCreditInvoiceStatus.PENDING.value)
    if max_cfs_account_id:
        for invoice, cfs_account, _ in results:
            assert cfs_account.id == max_cfs_account_id
    assert len(results) == pending_count
    results = EFTTask.get_eft_credit_invoice_links_by_status(EFTCreditInvoiceStatus.PENDING_REFUND.value)
    assert len(results) == pending_refund_count
    if test_name == 'invoice_refund_flow':
        results = EFTTask.get_eft_credit_invoice_links_by_status(EFTCreditInvoiceStatus.CANCELLED.value)
        assert len(results) == 1


def test_link_electronic_funds_transfers(session):
    """Test link electronic funds transfers."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(payment_account=payment_account, payment_method_code=PaymentMethod.EFT.value,
                              status_code=InvoiceStatus.APPROVED.value, total=10)
    invoice_reference = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(payment_account_id=payment_account.id, payment_method_code=PaymentMethod.EFT.value,
                    invoice_amount=351.50)
    eft_credit = factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id)
    credit_invoice_link = factory_create_eft_credit_invoice_link(invoice_id=invoice.id, eft_credit_id=eft_credit.id,
                                                                 link_group_id=1, amount=5)
    credit_invoice_link2 = factory_create_eft_credit_invoice_link(invoice_id=invoice.id, eft_credit_id=eft_credit.id,
                                                                  link_group_id=1, amount=5)
    eft_historical = factory_create_eft_shortname_historical(
        payment_account_id=payment_account.id,
        short_name_id=short_name_id,
        related_group_link_id=1
    )
    assert eft_historical.hidden
    assert eft_historical.is_processing

    cfs_account = CfsAccountModel.find_effective_by_payment_method(
        payment_account.id, PaymentMethod.EFT.value)

    with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_cfs:
        EFTTask.link_electronic_funds_transfers_cfs()
        mock_create_cfs.assert_called()

    assert cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert invoice_reference.status_code == InvoiceReferenceStatus.COMPLETED.value
    receipt = ReceiptModel.find_all_receipts_for_invoice(invoice.id)[0]
    assert receipt
    assert receipt.receipt_amount == credit_invoice_link.amount + credit_invoice_link2.amount
    assert receipt.invoice_id == invoice.id
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value
    assert invoice.paid == credit_invoice_link.amount + credit_invoice_link2.amount
    assert invoice.payment_date
    assert credit_invoice_link.status_code == EFTCreditInvoiceStatus.COMPLETED.value
    assert credit_invoice_link2.status_code == EFTCreditInvoiceStatus.COMPLETED.value

    assert not eft_historical.hidden
    assert not eft_historical.is_processing


def test_reverse_electronic_funds_transfers(session):
    """Test reverse electronic funds transfers."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    receipt_number = '1111R'
    invoice_number = '1234'

    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(payment_account=payment_account, total=30,
                              status_code=InvoiceStatus.PAID.value,
                              payment_method_code=PaymentMethod.EFT.value)

    factory_payment(payment_account_id=payment_account.id, payment_method_code=PaymentMethod.EFT.value,
                    invoice_amount=351.50, invoice_number=invoice_number)
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    invoice_reference = factory_invoice_reference(invoice_id=invoice.id,
                                                  status_code=InvoiceReferenceStatus.COMPLETED.value,
                                                  invoice_number=invoice_number)
    eft_credit = factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id)
    cil = factory_create_eft_credit_invoice_link(invoice_id=invoice.id,
                                                 status_code=EFTCreditInvoiceStatus.PENDING_REFUND.value,
                                                 eft_credit_id=eft_credit.id,
                                                 amount=30)
    factory_receipt(invoice.id, receipt_number)

    refund_requested_invoice = factory_invoice(payment_account=payment_account, total=30,
                                               status_code=InvoiceStatus.REFUND_REQUESTED.value,
                                               payment_method_code=PaymentMethod.EFT.value)

    factory_create_eft_credit_invoice_link(invoice_id=refund_requested_invoice.id,
                                           status_code=EFTCreditInvoiceStatus.CANCELLED.value,
                                           eft_credit_id=eft_credit.id,
                                           amount=30)
    invoice_reference2 = factory_invoice_reference(invoice_id=refund_requested_invoice.id,
                                                   status_code=InvoiceReferenceStatus.ACTIVE.value,
                                                   invoice_number=invoice_number)
    refund_requested_invoice2 = factory_invoice(payment_account=payment_account, total=30,
                                                status_code=InvoiceStatus.REFUND_REQUESTED.value,
                                                payment_method_code=PaymentMethod.EFT.value)

    factory_create_eft_credit_invoice_link(invoice_id=refund_requested_invoice2.id,
                                           status_code=EFTCreditInvoiceStatus.PENDING_REFUND.value,
                                           eft_credit_id=eft_credit.id,
                                           amount=30)
    invoice_reference3 = factory_invoice_reference(invoice_id=refund_requested_invoice2.id,
                                                   status_code=InvoiceReferenceStatus.COMPLETED.value,
                                                   invoice_number=invoice_number)
    eft_historical = factory_create_eft_shortname_historical(
        payment_account_id=payment_account.id,
        short_name_id=short_name_id,
        related_group_link_id=1,
        transaction_type=EFTHistoricalTypes.STATEMENT_REVERSE.value
    )
    assert eft_historical.hidden
    assert eft_historical.is_processing

    session.commit()

    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_reverse:
        with patch('pay_api.services.CFSService.adjust_invoice') as mock_adjust_invoice:
            EFTTask.reverse_electronic_funds_transfers_cfs()
            mock_adjust_invoice.assert_called()
            mock_reverse.assert_called()

    assert invoice_reference.status_code == InvoiceReferenceStatus.ACTIVE.value
    assert len(ReceiptModel.find_all_receipts_for_invoice(invoice.id)) == 0
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value
    assert invoice.paid == 0
    assert invoice.payment_date is None
    assert cil.status_code == EFTCreditInvoiceStatus.REFUNDED.value

    assert not eft_historical.hidden
    assert not eft_historical.is_processing

    assert refund_requested_invoice.invoice_status_code == InvoiceStatus.REFUNDED.value
    assert invoice_reference2.status_code == InvoiceReferenceStatus.CANCELLED.value
    assert refund_requested_invoice2.invoice_status_code == InvoiceStatus.REFUNDED.value
    assert invoice_reference3.status_code == InvoiceReferenceStatus.CANCELLED.value


def test_unlock_overdue_accounts(session):
    """Test unlock overdue account events."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    payment_account.has_overdue_invoices = datetime.now(tz=timezone.utc)
    invoice_1 = factory_invoice(payment_account=payment_account, payment_method_code=PaymentMethod.EFT.value, total=10)
    invoice_1.invoice_status_code = InvoiceStatus.OVERDUE.value
    invoice_1.save()
    factory_invoice_reference(invoice_id=invoice_1.id)
    eft_credit = factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id)
    factory_create_eft_credit_invoice_link(invoice_id=invoice_1.id, eft_credit_id=eft_credit.id, amount=10)

    # Create second overdue invoice and confirm unlock is not double called on a payment account
    invoice_2 = factory_invoice(payment_account=payment_account, payment_method_code=PaymentMethod.EFT.value, total=10)
    invoice_2.invoice_status_code = InvoiceStatus.OVERDUE.value
    invoice_2.save()
    factory_invoice_reference(invoice_id=invoice_2.id)
    factory_create_eft_credit_invoice_link(invoice_id=invoice_2.id, eft_credit_id=eft_credit.id, amount=10)

    with patch('utils.auth_event.AuthEvent.publish_unlock_account_event') as mock_unlock:
        EFTTask.link_electronic_funds_transfers_cfs()
        assert payment_account.has_overdue_invoices is None
        mock_unlock.assert_called_once()
        mock_unlock.assert_called_with(payment_account)


def test_handle_unlinked_refund_requested_invoices(session):
    """Test handle unlinked refund requested invoices."""
    auth_account_id, eft_file, short_name_id, eft_transaction_id = setup_eft_credit_invoice_links_test()
    eft_credit = factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id)
    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    invoice_1 = factory_invoice(payment_account=payment_account, status_code=InvoiceStatus.REFUND_REQUESTED.value,
                                payment_method_code=PaymentMethod.EFT.value, total=10).save()
    factory_invoice_reference(invoice_id=invoice_1.id).save()
    factory_create_eft_credit_invoice_link(invoice_id=invoice_1.id, eft_credit_id=eft_credit.id, amount=10)
    invoice_2 = factory_invoice(payment_account=payment_account, status_code=InvoiceStatus.REFUND_REQUESTED.value,
                                payment_method_code=PaymentMethod.EFT.value, total=10).save()
    invoice_ref_2 = factory_invoice_reference(invoice_id=invoice_2.id).save()
    invoice_3 = factory_invoice(payment_account=payment_account, status_code=InvoiceStatus.REFUND_REQUESTED.value,
                                payment_method_code=PaymentMethod.EFT.value, total=10).save()
    with patch('pay_api.services.CFSService.adjust_invoice') as mock_adjust_invoice:
        EFTTask.handle_unlinked_refund_requested_invoices()
        mock_adjust_invoice.assert_called()
        # Has CIL so it's excluded
        assert invoice_1.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
        # Has no CIL and invoice reference
        assert invoice_2.invoice_status_code == InvoiceStatus.REFUNDED.value
        assert invoice_2.refund_date
        assert invoice_2.refund
        assert invoice_ref_2.status_code == InvoiceReferenceStatus.CANCELLED.value
        # no invoice reference
        assert invoice_3.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
