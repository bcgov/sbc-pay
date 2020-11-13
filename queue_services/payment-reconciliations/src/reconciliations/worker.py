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
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.services.payment_transaction import publish_response
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, TransactionStatus)
from sentry_sdk import capture_message

from reconciliations import config
from reconciliations.minio import get_object

from .enums import Column, SourceTransaction, Status, TargetTransaction

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
        if event_message.get('type', None) == 'bc.registry.payment.paymentFileUploaded':
            # Handle payment file uploaded event
            _update_payment_details(event_message)
        else:
            raise Exception('Invalid type')


async def cb_subscription_handler(msg: nats.aio.client.Msg):
    """Use Callback to process Queue Msg objects."""
    try:
        logger.info('Received raw message seq:%s, data=  %s', msg.sequence, msg.data.decode())
        event_message = json.loads(msg.data.decode('utf-8'))
        logger.debug('Event Message Received: %s', event_message)
        await process_event(event_message, FLASK_APP)
    except Exception:  # pylint: disable=broad-except
        # Catch Exception so that any error is still caught and the message is removed from the queue
        logger.error('Queue Error: %s', json.dumps(event_message), exc_info=True)


def _update_payment_details(msg: Dict[str, any]):
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
        # Handle invoices
        if target_txn := _get_row_value(row, Column.TARGET_TXN) == TargetTransaction.INV.value:
            inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
            logger.debug('Processing invoice :  %s', inv_number)
            payment: PaymentModel = db.session.query(PaymentModel). \
                filter(PaymentModel.invoice_number == inv_number). \
                filter(PaymentModel.payment_status_code == PaymentStatus.CREATED.value). \
                one_or_none()
            inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
                filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.ACTIVE.value). \
                filter(InvoiceReferenceModel.invoice_number == inv_number). \
                all()

            payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(payment.payment_account_id)

            if target_txn_status := _get_row_value(row, Column.TARGET_TXN_STATUS) == Status.PAID.value:
                logger.debug('Fully PAID payment.')
                _process_paid_invoices(inv_references, payment, row)
                _publish_mailer_events('PaymentSuccess', payment_account, row)
            elif target_txn_status == Status.NOT_PAID.value:
                logger.info('NOT PAID. NSF identified.')
                # NSF Condition. Publish to account events for NSF.
                _process_failed_payments(payment, row)
                # Send mailer and account events to update status and send email notification
                _publish_account_events('PaymentFailed', payment_account, row)
                _publish_mailer_events('PaymentFailed', payment_account, row)
            elif target_txn_status == Status.PARTIAL.value:
                logger.info('Partially PAID.')
                _process_partial_payments(inv_references, payment, row)
                _publish_mailer_events('PartiallyPaid', payment_account, row)

        elif target_txn == TargetTransaction.RECEIPT.value and target_txn_status == Status.ON_ACC.value:
            logger.info('Applying credit to account %s.', payment_account.auth_account_id)
            # Apply credit to the account
            _process_account_credits(row)
            _publish_mailer_events('CreditCreated', payment_account, row)

        else:
            # For any other transactions like CM, DM log error and continue.
            # TODO change here when system is ready to accept EFT Receipts, Credits and Debits
            logger.error('Target Transaction Type is received as %s, and cannot process %s.', target_txn, msg)
            capture_message('Target Transaction Type is received as {target_txn}, and cannot process {msg}.'.format(
                target_txn=target_txn, msg=msg), level='error')
            # Continue processing

        # Commit the transaction and process next row.
        db.session.commit()


def _process_paid_invoices(inv_references, payment, row):
    """Process PAID invoices.

    Update invoices as PAID
    Update payment as COMPLETED
    Update invoice_reference as COMPLETED
    Update payment_transaction as COMPLETED.
    """
    if paid_amount := float(_get_row_value(row, Column.APP_AMOUNT)) != payment.invoice_amount:
        logger.error('Invoice amount received %s, but expected %s.', paid_amount, payment.invoice_amount)
        capture_message('Invoice amount received {paid_amount}, but expected {exp_amount}.'.format(
            paid_amount=paid_amount, exp_amount=payment.invoice_amount), level='error')

        raise Exception('Invalid Account Number')

    payment.payment_status_code = PaymentStatus.COMPLETED.value
    payment.paid_amount = paid_amount
    receipt_date: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%m%d%Y')
    receipt_number: str = _get_row_value(row, Column.APP_ID)

    txn: PaymentTransactionModel = _find_or_create_active_transaction(payment)
    txn.status_code = TransactionStatus.COMPLETED.value
    txn.transaction_end_time = datetime.now()

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
        if _get_row_value(row, Column.SOURCE_TXN) == SourceTransaction.ONLINE_BANKING.value:
            logger.debug('Publishing payment event for OB. Invoice : %s', inv.id)
            _publish_payment_event(txn, inv)


def _process_partial_payments(inv_references, payment, row):
    """Process partial payments.

    Update Payment as COMPLETED.
    Update Transaction is COMPLETED.
    Update Invoice as PARTIAL.
    """
    # Can occur for Online Banking and EFT/Wire. Handling only Online Banking, may need change when EFT is implemented.
    payment.payment_status_code = PaymentStatus.COMPLETED.value
    payment.paid_amount = float(_get_row_value(row, Column.APP_AMOUNT))
    receipt_date: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%m%d%Y')
    receipt_number: str = _get_row_value(row, Column.APP_ID)

    txn = _find_or_create_active_transaction(payment)
    txn.status_code = TransactionStatus.COMPLETED.value
    txn.transaction_end_time = datetime.now()

    for inv_ref in inv_references:
        inv: InvoiceModel = InvoiceModel.find_by_id(inv_ref.invoice_id)
        _validate_account(inv, row)
        logger.debug('Partial Invoice. Invoice Reference ID : %s, invoice ID : %s', inv_ref.id, inv_ref.invoice_id)
        inv.invoice_status_code = InvoiceStatus.PARTIAL.value
        inv.paid = payment.paid_amount

        # Create Receipt records
        receipt: ReceiptModel = ReceiptModel()
        receipt.receipt_date = receipt_date
        receipt.receipt_amount = payment.paid_amount  # Adding payment amount, as Online Banking is 1-1.
        receipt.invoice_id = inv.id
        receipt.receipt_number = receipt_number
        db.session.add(receipt)


def _process_failed_payments(payment, row):
    """Update the payment status as Failed."""
    payment.payment_status_code = PaymentStatus.FAILED.value
    payment.paid_amount = float(_get_row_value(row, Column.APP_AMOUNT))

    txn: PaymentTransactionModel = _find_or_create_active_transaction(payment)
    txn.status_code = TransactionStatus.FAILED.value
    txn.transaction_end_time = datetime.now()


def _process_account_credits(row: Dict[str, str]):
    """Apply credit to the account."""
    account_number: str = _get_row_value(row, Column.CUSTOMER_ACC)
    payment_account: PaymentAccountModel = db.session.query(PaymentAccountModel) \
        .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
        .filter(CfsAccountModel.cfs_account == account_number) \
        .filter(CfsAccountModel.status == CfsAccountStatus.value).one_or_none()
    payment_account.credit = float(_get_row_value(row, Column.TARGET_TXN_OUTSTANDING))


def _find_or_create_active_transaction(payment) -> PaymentTransactionModel:
    """Find active transaction, else start a new transaction.

    For partially paid invoices, there won't be any active transactions.
    """
    txn: PaymentTransactionModel = PaymentTransactionModel.find_active_by_payment_id(payment.id)
    if not txn:
        txn = PaymentTransactionModel()
        txn.status_code = TransactionStatus.CREATED.value
        txn.payment_id = payment.id
        txn.transaction_start_time = datetime.now()
        db.session.add(txn)
    return txn


def _validate_account(inv: InvoiceModel, row: Dict[str, str]):
    """Validate any mismatch in account number."""
    # This should never happen, just in case
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(inv.cfs_account_id)
    if account_number := _get_row_value(row, Column.CUSTOMER_ACC) != cfs_account.cfs_account:
        logger.error('Customer Account received as %s, but expected %s.', account_number, cfs_account.cfs_account)
        capture_message('Customer Account received as {account_number}, but expected {cfs_account}.'.format(
            account_number=account_number, cfs_account=cfs_account.cfs_account), level='error')

        raise Exception('Invalid Account Number')


def _publish_payment_event(transaction: PaymentTransactionModel, inv: InvoiceModel):
    """Publish payment message to the queue."""
    PaymentTransactionService.publish_status(transaction, inv)


def _publish_mailer_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(message_type, pay_account, row)

    try:
        publish_response(payload=payload,
                         client_name=APP_CONFIG.NATS_MAILER_CLIENT_NAME,
                         subject=APP_CONFIG.NATS_MAILER_SUBJECT)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(e)
        logger.warning(
            'Notification to Queue failed for the Account Mailer %s - %s', pay_account.auth_account_id,
            pay_account.auth_account_name)
        raise


def _publish_account_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(message_type, pay_account, row)

    try:
        publish_response(payload=payload,
                         client_name=APP_CONFIG.NATS_ACCOUNT_CLIENT_NAME,
                         subject=APP_CONFIG.NATS_ACCOUNT_SUBJECT)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Account %s - %s', pay_account.auth_account_id,
                       pay_account.auth_account_name)
        raise


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
    return row.get(key.value)
