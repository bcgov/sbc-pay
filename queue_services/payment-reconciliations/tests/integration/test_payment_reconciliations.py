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
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, PaymentStatus, TransactionStatus

from reconciliations.enums import SourceTransaction, Status, TargetTransaction

from .factory import (
    factory_create_online_banking_account, factory_create_pad_account, factory_invoice, factory_invoice_reference,
    factory_payment, factory_payment_line_item, factory_payment_transaction)
from .utils import create_and_upload_settlement_file, helper_add_event_to_queue


@pytest.mark.asyncio
async def test_online_banking_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future):
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
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()

    payment = factory_payment(pay_account=pay_account, invoice_number=invoice_number, invoice_amount=invoice.total)
    txn: PaymentTransactionModel = factory_payment_transaction(payment.id)

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    date = datetime.now().strftime('%m%d%Y')
    row = ['BOLP', SourceTransaction.ONLINE_BANKING.value, 100001, 1234567890, date, payment.invoice_amount, '1234',
           TargetTransaction.INV.value, invoice_number,
           payment.invoice_amount, 0, Status.PAID.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice = InvoiceModel.find_by_id(invoice.id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value
    updated_payment: PaymentModel = PaymentModel.find_by_id(payment.id)
    assert updated_payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert updated_payment.paid_amount == payment.invoice_amount

    updated_txn = PaymentTransactionModel.find_by_id(txn.id)
    assert updated_txn.status_code == TransactionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_online_banking_under_payment(session, app, stan_server, event_loop, client_id, events_stan, future):
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
    pay_account: PaymentAccountModel = factory_create_online_banking_account(status=CfsAccountStatus.ACTIVE.value)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value)
    factory_payment_line_item(invoice_id=invoice.id, filing_fees=90.0,
                              service_fees=10.0, total=90.0)
    invoice_number = '1234567890'
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()

    payment = factory_payment(pay_account=pay_account, invoice_number=invoice_number, invoice_amount=invoice.total)
    txn: PaymentTransactionModel = factory_payment_transaction(payment.id)

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    paid_amount = 10
    # Settlement row
    date = datetime.now().strftime('%m%d%Y')
    row = ['BOLP', SourceTransaction.ONLINE_BANKING.value, 100001, 1234567890, date, paid_amount, '1234',
           TargetTransaction.INV.value, invoice_number,
           payment.invoice_amount, payment.invoice_amount - paid_amount, Status.PARTIAL.value]
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)

    assert updated_invoice.invoice_status_code == InvoiceStatus.PARTIAL.value

    assert updated_invoice.paid == paid_amount
    updated_payment: PaymentModel = PaymentModel.find_by_id(payment.id)
    assert updated_payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert updated_payment.paid_amount == paid_amount

    updated_txn = PaymentTransactionModel.find_by_id(txn.id)
    assert updated_txn.status_code == TransactionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_pad_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future):
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
    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value)
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
    total = invoice1.total + invoice2.total
    payment = factory_payment(pay_account=pay_account, invoice_number=invoice_number, invoice_amount=total)
    txn: PaymentTransactionModel = factory_payment_transaction(payment.id)

    # Create a settlement file and publish.
    file_name: str = 'cas_settlement_file.csv'
    # Settlement row
    receipt_number = 1234567890
    date = datetime.now().strftime('%m%d%Y')
    row = ['PADP', SourceTransaction.PAD.value, 100001, receipt_number, date, payment.invoice_amount, '1234',
           'INV', invoice_number,
           payment.invoice_amount, 0, 'PAID']
    create_and_upload_settlement_file(file_name, [row])
    await helper_add_event_to_queue(events_stan, file_name=file_name)

    # The invoice should be in PAID status and Payment should be completed
    updated_invoice1 = InvoiceModel.find_by_id(invoice1.id)
    assert updated_invoice1.invoice_status_code == InvoiceStatus.PAID.value
    updated_invoice2 = InvoiceModel.find_by_id(invoice2.id)
    assert updated_invoice2.invoice_status_code == InvoiceStatus.PAID.value

    updated_payment: PaymentModel = PaymentModel.find_by_id(payment.id)
    assert updated_payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert updated_payment.paid_amount == payment.invoice_amount

    rcpt1: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice1.id, receipt_number)
    rcpt2: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice2.id, receipt_number)
    assert rcpt1
    assert rcpt2
    assert rcpt1.receipt_date == rcpt2.receipt_date

    updated_txn = PaymentTransactionModel.find_by_id(txn.id)
    assert updated_txn.status_code == TransactionStatus.COMPLETED.value
