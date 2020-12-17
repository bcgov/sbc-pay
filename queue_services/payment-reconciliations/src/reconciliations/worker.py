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
"""The unique worker functionality for this service is contained here.

The entry-point is the **cb_subscription_handler**

The design and flow leverage a few constraints that are placed upon it
by NATS Streaming and using AWAIT on the default loop.
- NATS streaming queues require one message to be processed at a time.
- AWAIT on the default loop effectively runs synchronously

If these constraints change, the use of Flask-SQLAlchemy would need to change.
Flask-SQLAlchemy currently allows the base model to be changed, or reworking
the model to a standalone SQLAlchemy usage with an async engine would need
to be pursued.
"""
import csv
import json
import os
from datetime import datetime
from typing import Dict, List

import nats
from entity_queue_common.service import QueueServiceManager
from entity_queue_common.service_utils import QueueException, logger
from flask import Flask
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.services.queue_publisher import publish
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus)
from pay_api.utils.util import get_pay_subject_name
from sentry_sdk import capture_message

from reconciliations import config
from reconciliations.minio import get_object

from .enums import Column, RecordType, SourceTransaction, Status, TargetTransaction


qsm = QueueServiceManager()  # pylint: disable=invalid-name
APP_CONFIG = config.get_named_config(os.getenv('DEPLOYMENT_ENV', 'production'))
FLASK_APP = Flask(__name__)
FLASK_APP.config.from_object(APP_CONFIG)
db.init_app(FLASK_APP)


async def process_event(event_message, flask_app):
    """Render the payment status."""
    if not flask_app:
        raise QueueException('Flask App not available.')

    with flask_app.app_context():
        if event_message.get('type', None) == 'bc.registry.payment.casSettlementUploaded':
            await _reconcile_payments(event_message)
        else:
            raise Exception('Invalid type')


async def cb_subscription_handler(msg: nats.aio.client.Msg):
    """Use Callback to process Queue Msg objects."""
    try:
        logger.info('Received raw message seq:%s, data=  %s', msg.sequence, msg.data.decode())
        event_message = json.loads(msg.data.decode('utf-8'))
        logger.debug('Event Message Received: %s', event_message)
        await process_event(event_message, FLASK_APP)
    except Exception as e:  # pylint: disable=broad-except
        # Catch Exception so that any error is still caught and the message is removed from the queue
        logger.error('Queue Error: %s', json.dumps(event_message), exc_info=True)
        logger.error(e)


def _create_payment_records(csv_content: str):
    """Create payment records by grouping the lines with target transaction number."""
    # Iterate the rows and create a dict with key as the source transaction number.
    source_txns: Dict[str, List[Dict[str, str]]] = {}
    for row in csv.DictReader(csv_content.splitlines()):
        # Convert lower case keys to avoid any key mismatch
        row = dict((k.lower(), v) for k, v in row.items())
        source_txn_number = _get_row_value(row, Column.SOURCE_TXN_NO)
        if not source_txns.get(source_txn_number):
            source_txns[source_txn_number] = [row]
        else:
            source_txns[source_txn_number].append(row)
    # Iterate the grouped source transactions and create payment record.
    # For PAD payments, create one payment record per row
    # For Online Banking payments, add up the ONAC receipts and payments against invoices.
    # For EFT, WIRE, Drawdown balance transfer mark the payment as COMPLETED
    # For Credit Memos, do nothing.
    for source_txn_number, payment_lines in source_txns.items():
        settlement_type: str = _get_settlement_type(payment_lines)
        if settlement_type in (RecordType.PAD.value, RecordType.PADR.value, RecordType.PAYR.value):
            for row in payment_lines:
                inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
                invoice_amount = float(_get_row_value(row, Column.TARGET_TXN_ORIGINAL))
                completed_on: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%d-%b-%y')
                status = PaymentStatus.COMPLETED.value \
                    if _get_row_value(row, Column.TARGET_TXN_STATUS).lower() == Status.PAID.value.lower() \
                    else PaymentStatus.FAILED.value
                paid_amount = float(
                    _get_row_value(row, Column.APP_AMOUNT)) if status == PaymentStatus.COMPLETED.value else 0

                _save_payment(completed_on, inv_number, invoice_amount, paid_amount, row, status,
                              PaymentMethod.PAD.value,
                              source_txn_number)
        elif settlement_type == RecordType.BOLP.value:
            # Add up the amount together for Online Banking
            paid_amount = 0
            inv_number = None
            invoice_amount = 0
            completed_on: datetime = datetime.strptime(_get_row_value(payment_lines[0], Column.APP_DATE), '%d-%b-%y')
            for row in payment_lines:
                paid_amount += float(_get_row_value(row, Column.APP_AMOUNT))

            # If the payment exactly covers the amount for invoice, then populate invoice amount and number
            if len(payment_lines) == 1:
                row = payment_lines[0]
                invoice_amount = float(_get_row_value(row, Column.TARGET_TXN_ORIGINAL))
                inv_number = _get_row_value(row, Column.TARGET_TXN_NO)

            _save_payment(completed_on, inv_number, invoice_amount, paid_amount, row, PaymentStatus.COMPLETED.value,
                          PaymentMethod.ONLINE_BANKING.value, source_txn_number)

        elif settlement_type == RecordType.EFTP.value:
            # Find the payment using receipt_number and mark it as COMPLETED
            payment: PaymentModel = db.session.query(PaymentModel).filter(
                PaymentModel.receipt_number == source_txn_number).one_or_none()
            payment.payment_status_code = PaymentStatus.COMPLETED.value

        db.session.commit()


def _save_payment(completed_on, inv_number, invoice_amount,  # pylint: disable=too-many-arguments
                  paid_amount, row, status, payment_method, receipt_number):
    # pylint: disable=import-outside-toplevel
    from pay_api.factory.payment_system_factory import PaymentSystemFactory

    payment_account = _get_payment_account(row)
    pay_service = PaymentSystemFactory.create_from_payment_method(payment_method)
    # If status is failed, which means NSF. We already have a COMPLETED payment record, find and update iit.
    payment: PaymentModel = None
    if status == PaymentStatus.FAILED.value:
        payment: PaymentModel = db.session.query(PaymentModel) \
            .filter(PaymentModel.invoice_number == inv_number,
                    PaymentModel.payment_status_code == PaymentStatus.COMPLETED.value) \
            .one_or_none()

    if not payment:
        payment = PaymentModel()
    payment.payment_method_code = pay_service.get_payment_method_code()
    payment.payment_status_code = status
    payment.payment_system_code = pay_service.get_payment_system_code()
    payment.invoice_number = inv_number
    payment.invoice_amount = invoice_amount
    payment.payment_account_id = payment_account.id
    payment.completed_on = completed_on
    payment.paid_amount = paid_amount
    payment.receipt_number = receipt_number
    db.session.add(payment)


async def _reconcile_payments(msg: Dict[str, any]):
    """Read the file and update payment details.

    1: Parse the file and create a dict per row for easy access.
    2: If the transaction is for invoice,
    2.1 : If transaction status is PAID, update invoice and payment statuses, publish to account mailer.
        For Online Banking invoices, publish message to the payment queue.
    2.2 : If transaction status is NOT PAID, update payment status, publish to account mailer and events to handle NSF.
    2.3 : If transaction status is PARTIAL, update payment and invoice status, publish to account mailer.
    3: If the transaction is On Account for Credit, apply the credit to the account.
    """
    file_name: str = msg.get('data').get('fileName')
    minio_location: str = msg.get('data').get('location')
    file = get_object(minio_location, file_name)
    content = file.data.decode('utf-8-sig')
    # Iterate the rows and create key value pair for each row
    for row in csv.DictReader(content.splitlines()):
        # Convert lower case keys to avoid any key mismatch
        row = dict((k.lower(), v) for k, v in row.items())
        logger.debug('Processing %s', row)

        # If PAD, lookup the payment table and mark status based on the payment status
        # If BCOL, lookup the invoices and set the status:
        # Create payment record by looking the receipt_number
        # If EFT/WIRE, lookup the invoices and set the status:
        # Create payment record by looking the receipt_number
        # PS : Duplicating some code to make the code more readable.
        if (record_type := _get_row_value(row, Column.RECORD_TYPE)) \
                in (RecordType.PAD.value, RecordType.PADR.value, RecordType.PAYR.value):
            # Handle invoices
            await _process_consolidated_invoices(row)
        elif record_type in (RecordType.BOLP.value, RecordType.EFTP.value):
            # EFT, WIRE and Online Banking are one-to-one invoice. So handle them in same way.
            await _process_unconsolidated_invoices(row)
        elif record_type in (RecordType.ONAC.value, RecordType.CMAP.value):
            await _process_credit_on_invoices(row)
        elif record_type == RecordType.ADJS.value:
            logger.info('Adjustment received for %s.', msg)
        else:
            # For any other transactions like DM, PAYR log error and continue.
            logger.error('Record Type is received as %s, and cannot process %s.', record_type, msg)
            capture_message('Record Type is received as {record_type}, and cannot process {msg}.'.format(
                record_type=record_type, msg=msg), level='error')
            # Continue processing

        # Commit the transaction and process next row.
        db.session.commit()

    # Create payment records for lines other than PAD
    _create_payment_records(content)
    # Create Credit Records.


async def _process_consolidated_invoices(row):
    target_txn_status = _get_row_value(row, Column.TARGET_TXN_STATUS)
    if (target_txn := _get_row_value(row, Column.TARGET_TXN)) == TargetTransaction.INV.value:
        inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
        logger.debug('Processing invoice :  %s', inv_number)

        inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
            filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.ACTIVE.value). \
            filter(InvoiceReferenceModel.invoice_number == inv_number). \
            all()

        payment_account: PaymentAccountModel = _get_payment_account(row)

        if target_txn_status.lower() == Status.PAID.value.lower():
            logger.debug('Fully PAID payment.')
            await _process_paid_invoices(inv_references, row)
            await _publish_mailer_events('PAD.PaymentSuccess', payment_account, row)
        elif target_txn_status.lower() == Status.NOT_PAID.value.lower():
            logger.info('NOT PAID. NSF identified.')
            # NSF Condition. Publish to account events for NSF.
            _process_failed_payments(row)
            # Send mailer and account events to update status and send email notification
            await _publish_account_events('lockAccount', payment_account, row)
        else:
            logger.error('Target Transaction Type is received as %s for PAD, and cannot process %s.', target_txn, row)
            capture_message(
                'Target Transaction Type is received as {target_txn} for PAD, and cannot process.'.format(
                    target_txn=target_txn), level='error')


async def _process_unconsolidated_invoices(row):
    target_txn_status = _get_row_value(row, Column.TARGET_TXN_STATUS)
    record_type = _get_row_value(row, Column.RECORD_TYPE)
    if (target_txn := _get_row_value(row, Column.TARGET_TXN)) == TargetTransaction.INV.value:
        inv_number = _get_row_value(row, Column.TARGET_TXN_NO)

        inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
            filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.ACTIVE.value). \
            filter(InvoiceReferenceModel.invoice_number == inv_number). \
            all()

        if len(inv_references) != 1:
            # There could be case where same invoice can appear as PAID in 2 lines, especially when there are credits.
            # Make sure there is one invoice_reference with completed status, else raise error.
            completed_inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
                filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.COMPLETED.value). \
                filter(InvoiceReferenceModel.invoice_number == inv_number). \
                all()
            logger.info('Found %s completed invoice references for invoice number %s', len(completed_inv_references),
                        inv_number)
            if len(completed_inv_references) != 1:
                logger.error('More than one or none invoice reference received for invoice number %s for %s',
                             inv_number, record_type)
                capture_message(
                    'More than one or none invoice reference received for invoice number {inv_number} for {record_type}'
                    .format(inv_number=inv_number, record_type=record_type), level='error')
        else:
            payment_account = _get_payment_account(row)
            # Handle fully PAID and Partially Paid scenarios.
            if target_txn_status.lower() == Status.PAID.value.lower():
                logger.debug('Fully PAID payment.')
                await _process_paid_invoices(inv_references, row)
                await _publish_mailer_events('OnlineBanking.PaymentSuccess', payment_account, row)
            elif target_txn_status.lower() == Status.PARTIAL.value.lower():
                logger.info('Partially PAID.')
                # As per validation above, get first and only inv ref
                _process_partial_paid_invoices(inv_references[0], row)
                await _publish_mailer_events('OnlineBanking.PartiallyPaid', payment_account, row)
            else:
                logger.error('Target Transaction Type is received as %s for %s, and cannot process.',
                             target_txn, record_type)
                capture_message(
                    'Target Transaction Type is received as {target_txn} for {record_type}, and cannot process.'
                    .format(target_txn=target_txn, record_type=record_type), level='error')


async def _process_credit_on_invoices(row):
    # Credit memo can happen for any type of accounts.
    target_txn_status = _get_row_value(row, Column.TARGET_TXN_STATUS)
    if _get_row_value(row, Column.TARGET_TXN) == TargetTransaction.INV.value:
        inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
        logger.debug('Processing invoice :  %s', inv_number)

        inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
            filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.ACTIVE.value). \
            filter(InvoiceReferenceModel.invoice_number == inv_number). \
            all()

        if target_txn_status.lower() == Status.PAID.value.lower():
            logger.debug('Fully PAID payment.')
            await _process_paid_invoices(inv_references, row)
        elif target_txn_status.lower() == Status.PARTIAL.value.lower():
            logger.info('Partially PAID using credit memo. Ignoring as the credit memo payment is already captured.')
        else:
            logger.error('Target Transaction status is received as %s for CMAP, and cannot process.', target_txn_status)
            capture_message(
                'Target Transaction status is received as {target_txn_status} for CMAP, and cannot process.'.format(
                    target_txn_status=target_txn_status), level='error')


async def _process_paid_invoices(inv_references, row):
    """Process PAID invoices.

    Update invoices as PAID
    Update payment as COMPLETED
    Update invoice_reference as COMPLETED
    Update payment_transaction as COMPLETED.
    """
    receipt_date: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%d-%b-%y')
    receipt_number: str = _get_row_value(row, Column.SOURCE_TXN_NO)
    for inv_ref in inv_references:
        inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
        # Find invoice, update status
        inv: InvoiceModel = InvoiceModel.find_by_id(inv_ref.invoice_id)
        _validate_account(inv, row)
        logger.debug('PAID Invoice. Invoice Reference ID : %s, invoice ID : %s', inv_ref.id, inv_ref.invoice_id)

        inv.invoice_status_code = InvoiceStatus.PAID.value
        inv.paid = inv.total
        # Create Receipt records
        receipt: ReceiptModel = ReceiptModel()
        receipt.receipt_date = receipt_date
        receipt.receipt_amount = inv.total
        receipt.invoice_id = inv.id
        receipt.receipt_number = receipt_number
        db.session.add(receipt)
        # Publish to the queue if it's an Online Banking payment
        if _get_row_value(row, Column.RECORD_TYPE) == RecordType.BOLP.value:
            logger.debug('Publishing payment event for OB. Invoice : %s', inv.id)
            await _publish_payment_event(inv)


def _process_partial_paid_invoices(inv_ref: InvoiceReferenceModel, row):
    """Process partial payments.

    Update Payment as COMPLETED.
    Update Transaction is COMPLETED.
    Update Invoice as PARTIAL.
    """
    receipt_date: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%d-%b-%y')
    receipt_number: str = _get_row_value(row, Column.APP_ID)

    inv: InvoiceModel = InvoiceModel.find_by_id(inv_ref.invoice_id)
    _validate_account(inv, row)
    logger.debug('Partial Invoice. Invoice Reference ID : %s, invoice ID : %s', inv_ref.id, inv_ref.invoice_id)
    inv.invoice_status_code = InvoiceStatus.PARTIAL.value
    inv.paid = inv.total - float(_get_row_value(row, Column.TARGET_TXN_OUTSTANDING))
    # Create Receipt records
    receipt: ReceiptModel = ReceiptModel()
    receipt.receipt_date = receipt_date
    receipt.receipt_amount = float(_get_row_value(row, Column.APP_AMOUNT))
    receipt.invoice_id = inv.id
    receipt.receipt_number = receipt_number
    db.session.add(receipt)


def _process_failed_payments(row):
    """Handle failed payments."""
    # 1. Set the cfs_account status as FREEZE.
    # 2. Call cfs api to Stop further PAD on this account.
    # 3. Reverse the invoice_reference status to ACTIVE, invoice status to SETTLEMENT_SCHED, and delete receipt.
    # 4. Create an NSF invoice for this account.
    # 5. Create invoice reference for the newly created NSF invoice.
    # 6. Adjust invoice in CFS to include NSF fees.
    inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
    # Set CFS Account Status.
    payment_account: PaymentAccountModel = _get_payment_account(row)
    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)
    logger.info('setting payment account id : %s status as FREEZE', payment_account.id)
    cfs_account.status = CfsAccountStatus.FREEZE.value
    # Call CFS to stop any further PAD transactions on this account.
    CFSService.suspend_cfs_account(cfs_account)
    # Find the invoice_reference for this invoice and mark it as ACTIVE.
    inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
        filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.COMPLETED.value). \
        filter(InvoiceReferenceModel.invoice_number == inv_number). \
        all()
    # Update status to ACTIVE, if it was marked COMPLETED
    for inv_reference in inv_references:
        inv_reference.status_code = InvoiceReferenceStatus.ACTIVE.value
        # Find receipt and delete it.
        receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(
            invoice_id=inv_reference.invoice_id
        )
        if receipt:
            db.session.delete(receipt)
        # Find invoice and update the status to SETTLEMENT_SCHED
        invoice: InvoiceModel = InvoiceModel.find_by_id(identifier=inv_reference.invoice_id)
        invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value

    # Create an invoice for NSF for this account
    invoice = _create_nsf_invoice(cfs_account, inv_number, payment_account)
    # Adjust CFS invoice
    CFSService.add_nsf_adjustment(cfs_account=cfs_account, inv_number=inv_number, amount=invoice.total)


def _process_account_credits(payment_account: PaymentAccountModel, row: Dict[str, str]):
    """Apply credit to the account."""
    logger.info('Current credit for account %s is %s', payment_account.auth_account_id, payment_account.credit)
    credit_amount: float = payment_account.credit or 0
    credit_amount += float(_get_row_value(row, Column.TARGET_TXN_ORIGINAL))
    payment_account.credit = credit_amount
    # TODO handle credits based on CAS feedback. Also add over payment to receipt table.


def _get_payment_account(row) -> PaymentAccountModel:
    account_number: str = _get_row_value(row, Column.CUSTOMER_ACC)
    payment_account: PaymentAccountModel = db.session.query(PaymentAccountModel) \
        .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
        .filter(CfsAccountModel.cfs_account == account_number) \
        .filter(
        CfsAccountModel.status.in_([CfsAccountStatus.ACTIVE.value, CfsAccountStatus.FREEZE.value])).one_or_none()

    return payment_account


def _validate_account(inv: InvoiceModel, row: Dict[str, str]):
    """Validate any mismatch in account number."""
    # This should never happen, just in case
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(inv.cfs_account_id)
    if (account_number := _get_row_value(row, Column.CUSTOMER_ACC)) != cfs_account.cfs_account:
        logger.error('Customer Account received as %s, but expected %s.', account_number, cfs_account.cfs_account)
        capture_message('Customer Account received as {account_number}, but expected {cfs_account}.'.format(
            account_number=account_number, cfs_account=cfs_account.cfs_account), level='error')

        raise Exception('Invalid Account Number')


async def _publish_payment_event(inv: InvoiceModel):
    """Publish payment message to the queue."""
    payment_event_payload = PaymentTransactionService.create_event_payload(invoice=inv,
                                                                           status_code=PaymentStatus.COMPLETED.value)
    try:

        await publish(payload=payment_event_payload, client_name=APP_CONFIG.NATS_PAYMENT_CLIENT_NAME,
                      subject=get_pay_subject_name(inv.corp_type_code, subject_format=APP_CONFIG.NATS_PAYMENT_SUBJECT))
    except Exception as e:  # pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Payment Event - %s', payment_event_payload)
        capture_message('Notification to Queue failed for the Payment Event {payment_event_payload}.'.format(
            payment_event_payload=payment_event_payload), level='error')


async def _publish_mailer_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(message_type, pay_account, row)
    try:
        await publish(payload=payload,
                      client_name=APP_CONFIG.NATS_MAILER_CLIENT_NAME,
                      subject=APP_CONFIG.NATS_MAILER_SUBJECT)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Account Mailer %s - %s', pay_account.auth_account_id,
                       payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')


async def _publish_account_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(message_type, pay_account, row)

    try:
        await publish(payload=payload,
                      client_name=APP_CONFIG.NATS_ACCOUNT_CLIENT_NAME,
                      subject=APP_CONFIG.NATS_ACCOUNT_SUBJECT)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Account %s - %s', pay_account.auth_account_id,
                       pay_account.auth_account_name)
        capture_message('Notification to Queue failed for the Account {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')


def _create_event_payload(message_type, pay_account, row):
    queue_data = {
        'accountId': pay_account.auth_account_id,
        'paymentMethod': _convert_payment_method(_get_row_value(row, Column.SOURCE_TXN)),
        'outstandingAmount': _get_row_value(row, Column.TARGET_TXN_OUTSTANDING),
        'originalAmount': _get_row_value(row, Column.TARGET_TXN_ORIGINAL),
        'amount': _get_row_value(row, Column.APP_AMOUNT)
    }
    payload = {
        'specversion': '1.x-wip',
        'type': f'bc.registry.payment.{message_type}',
        'source': f'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/{pay_account.auth_account_id}',
        'id': f'{pay_account.auth_account_id}',
        'time': f'{datetime.now()}',
        'datacontenttype': 'application/json',
        'data': queue_data
    }
    return payload


def _convert_payment_method(cfs_method: str) -> str:
    """Convert CFS type."""
    if cfs_method == SourceTransaction.ONLINE_BANKING.value:
        payment_method = PaymentMethod.ONLINE_BANKING.value
    elif cfs_method == SourceTransaction.PAD.value:
        payment_method = PaymentMethod.PAD.value
    else:
        payment_method = SourceTransaction(cfs_method).value

    return payment_method


def _get_row_value(row: Dict[str, str], key: Column) -> str:
    """Return row value from the row dictionary."""
    return row.get(key.value.lower())


def _create_nsf_invoice(cfs_account: CfsAccountModel, inv_number: str,
                        payment_account: PaymentAccountModel) -> InvoiceModel:
    """Create Invoice, line item and invoice referwnce records."""
    fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type_code='BCR',
                                                                                        filing_type_code='NSF')
    invoice = InvoiceModel(
        bcol_account=payment_account.bcol_account,
        payment_account_id=payment_account.id,
        cfs_account_id=cfs_account.id,
        invoice_status_code=InvoiceStatus.CREATED.value,
        total=fee_schedule.fee.amount,
        service_fees=0,
        paid=0,
        payment_method_code=PaymentMethod.CC.value,
        corp_type_code='BCR',
        created_on=datetime.now(),
        created_by='SYSTEM'
    )
    invoice = invoice.save()
    distribution: DistributionCodeModel = DistributionCodeModel.find_by_active_for_fee_schedule(
        fee_schedule.fee_schedule_id)

    line_item = PaymentLineItemModel(
        invoice_id=invoice.id,
        total=invoice.total,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        description=fee_schedule.filing_type.description,
        filing_fees=invoice.total,
        gst=0,
        priority_fees=0,
        pst=0,
        future_effective_fees=0,
        line_item_status_code=LineItemStatus.ACTIVE.value,
        service_fees=0,
        fee_distribution_id=distribution.distribution_code_id if distribution else 1)  # TODO
    line_item.save()

    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel(
        invoice_id=invoice.id,
        invoice_number=inv_number,
        reference_number=InvoiceReferenceModel.find_any_active_reference_by_invoice_number(
            invoice_number=inv_number).reference_number,
        status_code=InvoiceReferenceStatus.ACTIVE.value
    )
    inv_ref.save()

    return invoice


def _get_settlement_type(payment_lines) -> str:
    """Exclude ONAC, ADJS, PAYR, ONAP and return the record type."""
    settlement_type: str = None
    for row in payment_lines:
        # TODO Add BC Online Drawdown record type.
        if _get_row_value(row, Column.RECORD_TYPE) in \
                (RecordType.BOLP.value, RecordType.EFTP.value, RecordType.PAD.value, RecordType.PADR.value,
                 RecordType.PAYR.value):
            settlement_type = _get_row_value(row, Column.RECORD_TYPE)
            break
    return settlement_type
