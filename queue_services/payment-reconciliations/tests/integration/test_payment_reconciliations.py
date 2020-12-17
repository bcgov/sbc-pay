# Copyright © 2019 Province of British Columbia
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

from datetime import datetime

import pytest
from entity_queue_common.service_utils import subscribe_to_queue
from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus

from reconciliations.enums import RecordType, SourceTransaction, Status, TargetTransaction

from .factory import (
    factory_create_online_banking_account, factory_create_pad_account, factory_invoice, factory_invoice_reference,
    factory_payment, factory_payment_line_item, factory_receipt)
from .utils import create_and_upload_settlement_file, helper_add_event_to_queue


@pytest.mark.asyncio
async def test_online_banking_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future,
                                              mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value,
                                                                             cfs_account=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')
    receipt_number = '1234567890'
    row = [RecordType.BOLP.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date,
           total, cfs_account_number,
           TargetTransaction.INV.value, invoice_number,
           total, 0, Status.PAID.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number == invoice_number


@pytest.mark.asyncio
async def test_online_banking_reconciliations_over_payment(session, app, stan_server, event_loop, client_id,
                                                           events_stan, future,
                                                           mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value,
                                                                             cfs_account=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')
    receipt_number = '1234567890'
    over_payment_amount = 100
    inv_row = [RecordType.BOLP.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date, total,
               cfs_account_number, TargetTransaction.INV.value, invoice_number, total, 0, Status.PAID.value]
    credit_row = [RecordType.ONAC.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date,
                  over_payment_amount, cfs_account_number, TargetTransaction.INV.value, invoice_number,
                  over_payment_amount, 0, Status.ON_ACC.value]
    create_and_upload_settlement_file(file_name, [inv_row, credit_row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total + over_payment_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number is None  # No invoice_number if payment is not for 1 invoice


@pytest.mark.asyncio
async def test_online_banking_reconciliations_with_credit(session, app, stan_server, event_loop, client_id, events_stan,
                                                          future,
                                                          mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value,
                                                                             cfs_account=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')
    receipt_number = '1234567890'
    credit_amount = 10
    inv_row = [RecordType.BOLP.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date,
               total - credit_amount, cfs_account_number, TargetTransaction.INV.value, invoice_number, total, 0,
               Status.PAID.value]
    credit_row = [RecordType.ONAC.value, SourceTransaction.EFT_WIRE.value, '555566677', 100001, date, credit_amount,
                  cfs_account_number, TargetTransaction.INV.value, invoice_number, total, 0, Status.PAID.value]
    create_and_upload_settlement_file(file_name, [inv_row, credit_row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total - credit_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number == invoice_number


@pytest.mark.asyncio
async def test_online_banking_reconciliations_overflows_credit(session, app, stan_server, event_loop, client_id,
                                                               events_stan, future,
                                                               mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value,
                                                                             cfs_account=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')
    receipt_number = '1234567890'
    credit_amount = 10
    onac_amount = 100
    credit_row = [RecordType.ONAC.value, SourceTransaction.EFT_WIRE.value, '555566677', 100001, date, credit_amount,
                  cfs_account_number, TargetTransaction.INV.value, invoice_number, total, 0, Status.PAID.value]
    inv_row = [RecordType.BOLP.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date,
               total - credit_amount, cfs_account_number, TargetTransaction.INV.value, invoice_number, total, 0,
               Status.PAID.value]
    onac_row = [RecordType.ONAC.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date,
                onac_amount, cfs_account_number, TargetTransaction.RECEIPT.value, receipt_number, total, 0,
                Status.ON_ACC.value]

    create_and_upload_settlement_file(file_name, [inv_row, credit_row, onac_row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == total - credit_amount + onac_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number is None


@pytest.mark.asyncio
async def test_online_banking_under_payment(session, app, stan_server, event_loop, client_id, events_stan, future,
                                            mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value,
                                                                             cfs_account=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    paid_amount = 10
    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')
    receipt_number = '1234567890'

    row = [RecordType.BOLP.value, SourceTransaction.ONLINE_BANKING.value, receipt_number, 100001, date, paid_amount,
           cfs_account_number,
           TargetTransaction.INV.value, invoice_number,
           total, total - paid_amount, Status.PARTIAL.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PARTIAL.value
    assert updated_invoice.paid == paid_amount

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(receipt_number)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == paid_amount
    assert payment.receipt_number == receipt_number
    assert payment.payment_method_code == PaymentMethod.ONLINE_BANKING.value
    assert payment.invoice_number == invoice_number


@pytest.mark.asyncio
async def test_pad_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future, mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoices and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value,
                                                                  account_number=cfs_account_number)
    invoice1: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value)
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)

    invoice2: InvoiceModel = factory_invoice(payment_account=pay_account, total=200, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value)
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0,
                              service_fees=10.0, total=190.0)

    invoice_number = '1234567890'

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
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    receipt_number = '1234567890'
    date = datetime.now().strftime('%d-%b-%y')
    row = [RecordType.PAD.value, SourceTransaction.PAD.value, receipt_number, 100001, date, total,
           cfs_account_number,
           'INV', invoice_number,
           total, 0, Status.PAID.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

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


@pytest.mark.asyncio
async def test_pad_reconciliations_with_credit_memo(session, app, stan_server, event_loop,
                                                    client_id, events_stan, future, mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoices and related records
    # 3. Create CFS Invoice records
    # 4. Mimic some credits on the account
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value,
                                                                  account_number=cfs_account_number)
    invoice1: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value)
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)

    invoice2: InvoiceModel = factory_invoice(payment_account=pay_account, total=200, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value)
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0,
                              service_fees=10.0, total=190.0)

    invoice_number = '1234567890'

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
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    receipt_number = '1234567890'
    credit_memo_number = 'CM123'
    date = datetime.now().strftime('%d-%b-%y')
    credit_amount = 25

    credit_row = [RecordType.CMAP.value, SourceTransaction.CREDIT_MEMO.value, credit_memo_number, 100002, date,
                  credit_amount, cfs_account_number, 'INV', invoice_number, total, 0, Status.PAID.value]
    pad_row = [RecordType.PAD.value, SourceTransaction.PAD.value, receipt_number, 100001, date, total - credit_amount,
               cfs_account_number, 'INV', invoice_number, total, 0, Status.PAID.value]
    create_and_upload_settlement_file(file_name, [credit_row, pad_row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

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


@pytest.mark.asyncio
async def test_pad_nsf_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future,
                                       mock_publish):
    """Test Reconciliations worker for NSF."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoices and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value,
                                                                  account_number=cfs_account_number)
    invoice1: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value)
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)

    invoice2: InvoiceModel = factory_invoice(payment_account=pay_account, total=200, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value)
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0,
                              service_fees=10.0, total=190.0)

    invoice_number = '1234567890'

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
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    receipt_number = '1234567890'
    date = datetime.now().strftime('%d-%b-%y')
    row = [RecordType.PAD.value, SourceTransaction.PAD.value, receipt_number, 100001, date, 0, cfs_account_number,
           'INV', invoice_number,
           total, total, Status.NOT_PAID.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

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

    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(pay_account_id)
    assert cfs_account.status == CfsAccountStatus.FREEZE.value


@pytest.mark.asyncio
async def test_pad_reversal_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future,
                                            mock_publish):
    """Test Reconciliations worker for NSF."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoices and related records for a completed payment
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value,
                                                                  account_number=cfs_account_number)
    invoice1: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value,
                                             status_code=InvoiceStatus.PAID.value)
    factory_payment_line_item(invoice_id=invoice1.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)

    invoice2: InvoiceModel = factory_invoice(payment_account=pay_account, total=200, service_fees=10.0,
                                             payment_method_code=PaymentMethod.PAD.value,
                                             status_code=InvoiceStatus.PAID.value)
    factory_payment_line_item(invoice_id=invoice2.id, filing_fees=190.0,
                              service_fees=10.0, total=190.0)

    invoice_number = '1234567890'
    receipt_number = '9999999999'

    factory_invoice_reference(invoice_id=invoice1.id, invoice_number=invoice_number,
                              status_code=InvoiceReferenceStatus.COMPLETED.value)
    factory_invoice_reference(invoice_id=invoice2.id, invoice_number=invoice_number,
                              status_code=InvoiceReferenceStatus.COMPLETED.value)

    receipt_id1 = factory_receipt(invoice_id=invoice1.id, receipt_number=receipt_number).save().id
    receipt_id2 = factory_receipt(invoice_id=invoice2.id, receipt_number=receipt_number).save().id

    invoice1_id = invoice1.id
    invoice2_id = invoice2.id
    pay_account_id = pay_account.id

    total = invoice1.total + invoice2.total

    payment = factory_payment(pay_account=pay_account, paid_amount=total, invoice_amount=total,
                              invoice_number=invoice_number,
                              receipt_number=receipt_number, status=PaymentStatus.COMPLETED.value)
    pay_id = payment.id

    # Now publish message saying payment has been reversed.
    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')
    row = [RecordType.PADR.value, SourceTransaction.PAD.value, receipt_number, 100001, date, 0, cfs_account_number,
           'INV', invoice_number,
           total, total, Status.NOT_PAID.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

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

    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(pay_account_id)
    assert cfs_account.status == CfsAccountStatus.FREEZE.value

    # Receipt should be deleted
    assert ReceiptModel.find_by_id(receipt_id1) is None
    assert ReceiptModel.find_by_id(receipt_id2) is None


@pytest.mark.asyncio
async def test_eft_wire_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future,
                                        mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value,
                                                                             cfs_account=cfs_account_number)

    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()
    invoice_id = invoice.id
    total = invoice.total

    # Create a payment for EFT Wire
    eft_wire_receipt = 'RCPT0012345'
    paid_amount = 100
    PaymentModel(payment_method_code=PaymentMethod.EFT.value,
                 payment_status_code=PaymentStatus.CREATED.value,
                 payment_system_code='PAYBC',
                 payment_account_id=pay_account.id,
                 completed_on=datetime.now(),
                 paid_amount=paid_amount,
                 receipt_number=eft_wire_receipt).save()

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'

    # Settlement row
    date = datetime.now().strftime('%d-%b-%y')

    row = [RecordType.EFTP.value, SourceTransaction.EFT_WIRE.value, eft_wire_receipt, 100001, date, total,
           cfs_account_number, TargetTransaction.INV.value, invoice_number, total, 0, Status.PAID.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice_id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    payment: PaymentModel = PaymentModel.find_payment_by_receipt_number(eft_wire_receipt)
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.paid_amount == paid_amount
    assert payment.receipt_number == eft_wire_receipt
