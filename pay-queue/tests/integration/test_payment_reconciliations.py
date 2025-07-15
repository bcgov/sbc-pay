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

"""Tests to assure the Payment Reconciliation.

Test-Suite to ensure that the Payment Reconciliation queue service is working as expected.
"""
import logging
from datetime import datetime, timezone

import pytest
from pay_api.models import AppliedCredits as AppliedCreditsModel
from pay_api.models import CasSettlement as CasSettlementModel
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Credit as CreditModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_queue.enums import RecordType, SourceTransaction, Status, TargetTransaction

from .factory import (
    factory_create_online_banking_account,
    factory_create_pad_account,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_line_item,
    factory_receipt,
)
from .utils import add_file_event_to_queue_and_process, create_and_upload_settlement_file


def test_online_banking_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")
    receipt_number = "1234567890"
    row = [
        RecordType.BOLP.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        total,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number == invoice_number


def test_online_banking_reconciliations_over_payment(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")
    receipt_number = "1234567890"
    over_payment_amount = 100
    inv_row = [
        RecordType.BOLP.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        total,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    credit_row = [
        RecordType.ONAC.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        over_payment_amount,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        over_payment_amount,
        0,
        Status.ON_ACC.value,
    ]
    create_and_upload_settlement_file(file_name, [inv_row, credit_row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total + over_payment_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number is None  # No invoice_number if payment is not for 1 invoice


def test_online_banking_reconciliations_with_credit(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")
    receipt_number = "1234567890"
    credit_amount = 10
    inv_row = [
        RecordType.BOLP.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        total - credit_amount,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    credit_row = [
        RecordType.ONAC.value,
        SourceTransaction.EFT_WIRE.value,
        "555566677",
        100001,
        date,
        credit_amount,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [inv_row, credit_row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total - credit_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number == invoice_number


def test_online_banking_reconciliations_overflows_credit(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")
    receipt_number = "1234567890"
    credit_amount = 10
    onac_amount = 100
    credit_row = [
        RecordType.ONAC.value,
        SourceTransaction.EFT_WIRE.value,
        "555566677",
        100001,
        date,
        credit_amount,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    inv_row = [
        RecordType.BOLP.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        total - credit_amount,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    onac_row = [
        RecordType.ONAC.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        onac_amount,
        cfs_account_number,
        TargetTransaction.RECEIPT.value,
        receipt_number,
        total,
        0,
        Status.ON_ACC.value,
    ]

    create_and_upload_settlement_file(file_name, [inv_row, credit_row, onac_row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total - credit_amount + onac_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number is None


def test_online_banking_under_payment(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    paid_amount = 10
    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")
    receipt_number = "1234567890"

    row = [
        RecordType.BOLP.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        paid_amount,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        total - paid_amount,
        Status.PARTIAL.value,
    ]
    create_and_upload_settlement_file(file_name, [row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PARTIAL.value
    assert updated_invoice.paid == paid_amount

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == paid_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number == invoice_number


def test_pad_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoices and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice1 = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
    )
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0, service_fees=10.0, total=90.0)

    invoice2 = factory_invoice(
        payment_account=pay_account,
        total=200,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
    )
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0, service_fees=10.0, total=190.0)

    invoice_number = "1234567890"

    factory_invoice_reference(invoice_id=invoice1.id, invoice_number=invoice_number)
    factory_invoice_reference(invoice_id=invoice2.id, invoice_number=invoice_number)

    invoice1.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice2.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice1.save()
    invoice2.save()
    invoice1_id = invoice1.id
    invoice2_id = invoice2.id
    total = invoice1.total + invoice2.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    receipt_number = "1234567890"
    date = datetime.now().strftime("%d-%b-%y")
    row = [
        RecordType.PAD.value,
        SourceTransaction.PAD.value,
        receipt_number,
        100001,
        date,
        total,
        cfs_account_number,
        "INV",
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice1 = InvoiceModel.find_by_id(invoice1_id)
    assert updated_invoice1.invoice_status_code == InvoiceStatus.PAID.value
    updated_invoice2 = InvoiceModel.find_by_id(invoice2_id)
    assert updated_invoice2.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.PAD.value
    assert payment.invoice_number == invoice_number

    rcpt1: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice1_id, receipt_number)
    rcpt2: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice2_id, receipt_number)
    assert rcpt1
    assert rcpt2
    assert rcpt1.receipt_date == rcpt2.receipt_date


def test_pad_reconciliations_with_credit_memo(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoices and related records
    # 3. Create CFS Invoice records
    # 4. Mimic some credits on the account
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice1 = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
    )
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0, service_fees=10.0, total=90.0)

    invoice2 = factory_invoice(
        payment_account=pay_account,
        total=200,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
    )
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0, service_fees=10.0, total=190.0)

    invoice_number = "1234567890"

    factory_invoice_reference(invoice_id=invoice1.id, invoice_number=invoice_number)
    factory_invoice_reference(invoice_id=invoice2.id, invoice_number=invoice_number)

    invoice1.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice2.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice1.save()
    invoice2.save()
    invoice1_id = invoice1.id
    invoice2_id = invoice2.id
    total = invoice1.total + invoice2.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    receipt_number = "1234567890"
    credit_memo_number = "CM123"
    date = datetime.now().strftime("%d-%b-%y")
    credit_amount = 25

    credit_row = [
        RecordType.CMAP.value,
        SourceTransaction.CREDIT_MEMO.value,
        credit_memo_number,
        100002,
        date,
        credit_amount,
        cfs_account_number,
        "INV",
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    pad_row = [
        RecordType.PAD.value,
        SourceTransaction.PAD.value,
        receipt_number,
        100001,
        date,
        total - credit_amount,
        cfs_account_number,
        "INV",
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [credit_row, pad_row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice1 = InvoiceModel.find_by_id(invoice1_id)
    assert updated_invoice1.invoice_status_code == InvoiceStatus.PAID.value
    updated_invoice2 = InvoiceModel.find_by_id(invoice2_id)
    assert updated_invoice2.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total - credit_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.PAD.value
    assert payment.invoice_number == invoice_number

    rcpt1: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice1_id, receipt_number)
    rcpt2: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice2_id, receipt_number)
    assert rcpt1
    assert rcpt2
    assert rcpt1.receipt_date == rcpt2.receipt_date


def test_pad_nsf_reconciliations(session, app, client):
    """Test Reconciliations worker for NSF."""
    # 1. Create payment account
    # 2. Create invoices and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice1 = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
    )
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0, service_fees=10.0, total=90.0)

    invoice2 = factory_invoice(
        payment_account=pay_account,
        total=200,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
    )
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0, service_fees=10.0, total=190.0)

    invoice_number = "1234567890"

    factory_invoice_reference(invoice_id=invoice1.id, invoice_number=invoice_number)
    factory_invoice_reference(invoice_id=invoice2.id, invoice_number=invoice_number)

    invoice1.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice2.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice1.save()
    invoice2.save()
    invoice1_id = invoice1.id
    invoice2_id = invoice2.id
    pay_account_id = pay_account.id

    total = invoice1.total + invoice2.total

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    receipt_number = "1234567890"
    date = datetime.now().strftime("%d-%b-%y")
    row = [
        RecordType.PAD.value,
        SourceTransaction.PAD.value,
        receipt_number,
        100001,
        date,
        0,
        cfs_account_number,
        "INV",
        invoice_number,
        total,
        total,
        Status.NOT_PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in SETTLEMENT_SCHEDULED status and Payment should be FAILED
    updated_invoice1 = InvoiceModel.find_by_id(invoice1_id)
    assert updated_invoice1.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value
    updated_invoice2 = InvoiceModel.find_by_id(invoice2_id)
    assert updated_invoice2.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.FAILED.value
    assert payment.paid_amount == 0
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.PAD.value
    assert payment.invoice_number == invoice_number

    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_payment_method(
        pay_account_id, PaymentMethod.PAD.value
    )
    assert cfs_account.status == CfsAccountStatus.FREEZE.value
    assert pay_account.has_nsf_invoices


def test_pad_reversal_reconciliations(session, app, client):
    """Test Reconciliations worker for NSF."""
    # 1. Create payment account
    # 2. Create invoices and related records for a completed payment
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice1 = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
        status_code=InvoiceStatus.PAID.value,
    )
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0, service_fees=10.0, total=90.0)

    invoice2 = factory_invoice(
        payment_account=pay_account,
        total=200,
        service_fees=10.0,
        payment_method_code=PaymentMethod.PAD.value,
        status_code=InvoiceStatus.PAID.value,
    )
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0, service_fees=10.0, total=190.0)

    invoice_number = "1234567890"
    receipt_number = "9999999999"

    factory_invoice_reference(
        invoice_id=invoice1.id,
        invoice_number=invoice_number,
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    factory_invoice_reference(
        invoice_id=invoice2.id,
        invoice_number=invoice_number,
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )

    receipt_id1 = factory_receipt(invoice_id=invoice1.id, receipt_number=receipt_number).save().id
    receipt_id2 = factory_receipt(invoice_id=invoice2.id, receipt_number=receipt_number).save().id

    invoice1_id = invoice1.id
    invoice2_id = invoice2.id
    pay_account_id = pay_account.id

    total = invoice1.total + invoice2.total

    payment = factory_payment(
        pay_account=pay_account,
        paid_amount=total,
        invoice_amount=total,
        invoice_number=invoice_number,
        receipt_number=receipt_number,
        status=PaymentStatus.COMPLETED.value,
    )
    pay_id = payment.id

    # Now publish message saying payment has been reversed.
    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"
    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")
    row = [
        RecordType.PADR.value,
        SourceTransaction.PAD.value,
        receipt_number,
        100001,
        date,
        0,
        cfs_account_number,
        "INV",
        invoice_number,
        total,
        total,
        Status.NOT_PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in SETTLEMENT_SCHEDULED status and Payment should be FAILED
    updated_invoice1 = InvoiceModel.find_by_id(invoice1_id)
    assert updated_invoice1.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value
    updated_invoice2 = InvoiceModel.find_by_id(invoice2_id)
    assert updated_invoice2.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value

    payment: PaymentModel = PaymentModel.find_by_id(pay_id)
    assert payment.payment_status_code == PaymentStatus.FAILED.value
    assert payment.paid_amount == 0
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.PAD.value
    assert payment.invoice_number == invoice_number

    cfs_account = CfsAccountModel.find_effective_by_payment_method(pay_account_id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.FREEZE.value
    assert pay_account.has_nsf_invoices

    # Receipt should be deleted
    assert ReceiptModel.find_by_id(receipt_id1) is None
    assert ReceiptModel.find_by_id(receipt_id2) is None


@pytest.mark.skip(reason="This is handled in the eft-job, similar to routing slips.")
@pytest.mark.asyncio
async def test_eft_wire_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )

    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    receipt = "RCPT0012345"
    paid_amount = 100
    PaymentModel(
        payment_method_code=PaymentMethod.EFT.value,
        payment_status_code=PaymentStatus.CREATED.value,
        payment_system_code="PAYBC",
        payment_account_id=pay_account.id,
        payment_date=datetime.now(),
        paid_amount=paid_amount,
        receipt_number=receipt,
    ).save()

    # Create a settlement file and publish.
    file_name: str = "cas_settlement_file.csv"

    # Settlement row
    date = datetime.now().strftime("%d-%b-%y")

    row = [
        RecordType.EFTP.value,
        SourceTransaction.EFT_WIRE.value,
        receipt,
        100001,
        date,
        total,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == paid_amount
    assert payment.receipt_number == receipt


def test_credits(session, app, client, monkeypatch):
    """Test Reconciliations worker."""
    # 1. Create payment account.
    # 2. Create payment db record.
    # 3. Create a credit memo db record.
    # 4. Publish credit in settlement file.
    # 5. Mock CFS Response for the receipt and credit memo.
    # 6. Confirm the credit matches the records.
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )
    pay_account_id = pay_account.id
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)

    receipt_number = "RCPT0012345"
    onac_amount = 100
    cm_identifier = 1000
    cm_amount = 100
    cm_used_amount = 50
    PaymentModel(
        payment_method_code=PaymentMethod.EFT.value,
        payment_status_code=PaymentStatus.CREATED.value,
        payment_system_code="PAYBC",
        payment_account_id=pay_account.id,
        payment_date=datetime.now(),
        paid_amount=onac_amount,
        receipt_number=receipt_number,
    ).save()

    credit = CreditModel(
        cfs_identifier=cm_identifier,
        is_credit_memo=True,
        amount=cm_amount,
        remaining_amount=cm_amount,
        account_id=pay_account_id,
    ).save()
    credit_id = credit.id

    def mock_receipt(
        cfs_account: CfsAccountModel, receipt_number: str, return_none_if_404: bool = False
    ):  # pylint: disable=unused-argument; mocks of library methods
        return {"receipt_amount": onac_amount}

    def mock_cms(
        cfs_account: CfsAccountModel, cms_number: str, return_none_if_404: bool = False
    ):  # pylint: disable=unused-argument; mocks of library methods
        return {"amount_due": cm_amount - cm_used_amount}

    monkeypatch.setattr("pay_api.services.cfs_service.CFSService.get_receipt", mock_receipt)
    monkeypatch.setattr("pay_api.services.cfs_service.CFSService.get_cms", mock_cms)

    file_name = "cas_settlement_file.csv"
    date = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    date_str = date.strftime("%d-%b-%y")

    row = [
        RecordType.ONAC.value,
        SourceTransaction.EFT_WIRE.value,
        receipt_number,
        "100001",
        date_str,
        onac_amount,
        cfs_account_number,
        TargetTransaction.RECEIPT.value,
        receipt_number,
        onac_amount,
        0,
        Status.ON_ACC.value,
    ]

    credit_invoices_row = [
        RecordType.CMAP.value,
        SourceTransaction.CREDIT_MEMO.value,
        cm_identifier,
        "100003",
        date_str,
        2.5,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        100,
        0,
        Status.PAID.value,
    ]

    credit_invoices_row2 = [
        RecordType.CMAP.value,
        SourceTransaction.CREDIT_MEMO.value,
        cm_identifier,
        "100004",
        date_str,
        5.5,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        100,
        0,
        Status.PAID.value,
    ]

    create_and_upload_settlement_file(file_name, [row, credit_invoices_row, credit_invoices_row2])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    # Look up credit file and make sure the credits are recorded.
    pay_account = PaymentAccountModel.find_by_id(pay_account_id)
    assert pay_account.ob_credit == onac_amount + cm_amount - cm_used_amount
    credit = CreditModel.find_by_id(credit_id)
    assert credit.remaining_amount == cm_amount - cm_used_amount

    credit_invoices = AppliedCreditsModel.query.all()
    assert len(credit_invoices) == 2
    assert credit_invoices[0].account_id == pay_account.id
    assert credit_invoices[0].amount_applied == 2.5
    assert credit_invoices[0].application_id == 100003
    assert credit_invoices[0].cfs_account == cfs_account_number
    assert credit_invoices[0].cfs_identifier == str(cm_identifier)
    assert credit_invoices[0].created_on == date
    assert credit_invoices[0].credit_id == credit_id
    assert credit_invoices[0].invoice_number == invoice_number
    assert credit_invoices[0].invoice_amount == 100
    assert credit_invoices[1].amount_applied == 5.5
    assert credit_invoices[1].application_id == 100004
    assert credit_invoices[1].cfs_identifier == str(cm_identifier)
    assert credit_invoices[1].invoice_number == invoice_number
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice.paid
    assert invoice.paid == 100


def test_unconsolidated_invoices_errors(session, app, client, mocker):
    """Test error scenarios for unconsolidated invoices in the reconciliation worker."""
    cfs_account_number = "1234"
    pay_account = factory_create_online_banking_account(
        status=CfsAccountStatus.ACTIVE.value, cfs_account=cfs_account_number
    )

    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0)
    invoice_number = "1234567890"
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    error_messages = [{"error": "Test error message", "row": "row 2"}]
    mocker.patch(
        "pay_queue.services.payment_reconciliations._process_file_content",
        return_value=(True, error_messages),
    )
    mock_send_error_email = mocker.patch("pay_queue.services.payment_reconciliations.send_error_email")

    file_name: str = "BCR_PAYMENT_APPL_20240619.csv"
    date = datetime.now(tz=timezone.utc).isoformat()
    receipt_number = "1234567890"
    row = [
        RecordType.BOLP.value,
        SourceTransaction.ONLINE_BANKING.value,
        receipt_number,
        100001,
        date,
        total,
        cfs_account_number,
        TargetTransaction.INV.value,
        invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value

    mock_send_error_email.assert_called_once()
    call_args = mock_send_error_email.call_args
    email_params = call_args[0][0]
    assert email_params.subject == "Payment Reconciliation Failure"
    assert email_params.file_name == file_name
    assert email_params.minio_location == "payment-sftp"
    assert email_params.error_messages == error_messages
    assert email_params.table_name == CasSettlementModel.__tablename__


def test_pad_reconciliation_skips_paid_base_invoice_with_completed_consolidated(session, app, client, caplog):
    """Test reconciliation skips invoice row when a COMPLETED consolidated (-C) version exists."""
    cfs_account_number = "PAD_ACC_C_TEST"
    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)

    invoice = factory_invoice(
        payment_account=pay_account,
        total=50.0,
        service_fees=5.0,
        payment_method_code=PaymentMethod.PAD.value,
        status_code=InvoiceStatus.PAID.value,
    )
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=45.0, service_fees=5.0, total=45.0)
    invoice_id = invoice.id
    total = invoice.total

    base_invoice_number = "REG07401364"
    consolidated_invoice_number = "REG7401364-C"

    # - Base invoice reference is CANCELLED
    factory_invoice_reference(
        invoice_id=invoice.id, invoice_number=base_invoice_number, status_code=InvoiceReferenceStatus.CANCELLED.value
    )
    # - Consolidated invoice reference (-C) is COMPLETED (linking to the same invoice)
    factory_invoice_reference(
        invoice_id=invoice.id,
        invoice_number=consolidated_invoice_number,
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )

    file_name: str = "cas_settlement_consolidated_skip_test.csv"
    receipt_number = "PADRCPT001"
    date = datetime.now().strftime("%d-%b-%y")
    row = [
        RecordType.PAD.value,
        SourceTransaction.PAD.value,
        receipt_number,
        200001,
        date,
        total,
        cfs_account_number,
        TargetTransaction.INV.value,
        base_invoice_number,
        total,
        0,
        Status.PAID.value,
    ]
    create_and_upload_settlement_file(file_name, [row])

    caplog.set_level(logging.WARNING)

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.CAS_MESSAGE_TYPE.value,
    )

    expected_warning = (
        f"Invoice {base_invoice_number} not found as COMPLETED, "
        f"but consolidated version {consolidated_invoice_number} found as COMPLETED"
    )
    assert any(expected_warning in record.message for record in caplog.records if record.levelname == "WARNING")

    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment is not None, "Payment record should have been created"
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total
    assert payment.invoice_number == base_invoice_number

    receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id, receipt_number)
    assert receipt is None, "Receipt should not have been created by the skipped processing step"
