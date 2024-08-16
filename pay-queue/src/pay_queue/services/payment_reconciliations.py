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
"""Payment reconciliation file."""
import csv
import dataclasses
import json
import os
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Tuple

from flask import current_app
from jinja2 import Environment, FileSystemLoader
from pay_api.models import CasSettlement as CasSettlementModel
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Credit as CreditModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.services import gcp_queue_publisher
from pay_api.services.cfs_service import CFSService
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.services.non_sufficient_funds import NonSufficientFundsService
from pay_api.services.oauth_service import OAuthService
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.utils.constants import RECEIPT_METHOD_PAD_STOP
from pay_api.utils.enums import (
    AuthHeaderType, CfsAccountStatus, ContentType, InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod,
    PaymentStatus, QueueSources)
from pay_api.utils.util import get_topic_for_corp_type
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message

from pay_queue import config
from pay_queue.auth import get_token
from pay_queue.minio import get_object

from ..enums import Column, RecordType, SourceTransaction, Status, TargetTransaction


APP_CONFIG = config.get_named_config(os.getenv('DEPLOYMENT_ENV', 'production'))


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

                payment_date: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%d-%b-%y')
                status = PaymentStatus.COMPLETED.value \
                    if _get_row_value(row, Column.TARGET_TXN_STATUS).lower() == Status.PAID.value.lower() \
                    else PaymentStatus.FAILED.value
                paid_amount = 0
                if status == PaymentStatus.COMPLETED.value:
                    paid_amount = float(_get_row_value(row, Column.APP_AMOUNT))
                elif _get_row_value(row, Column.TARGET_TXN_STATUS).lower() == Status.PARTIAL.value.lower():
                    paid_amount = invoice_amount - float(_get_row_value(row, Column.TARGET_TXN_OUTSTANDING))

                _save_payment(payment_date, inv_number, invoice_amount, paid_amount, row, status,
                              PaymentMethod.PAD.value,
                              source_txn_number)
        elif settlement_type == RecordType.BOLP.value:
            # Add up the amount together for Online Banking
            paid_amount = 0
            inv_number = None
            invoice_amount = 0
            payment_date: datetime = datetime.strptime(_get_row_value(payment_lines[0], Column.APP_DATE), '%d-%b-%y')
            for row in payment_lines:
                paid_amount += float(_get_row_value(row, Column.APP_AMOUNT))

            # If the payment exactly covers the amount for invoice, then populate invoice amount and number
            if len(payment_lines) == 1:
                row = payment_lines[0]
                invoice_amount = float(_get_row_value(row, Column.TARGET_TXN_ORIGINAL))
                inv_number = _get_row_value(row, Column.TARGET_TXN_NO)

            _save_payment(payment_date, inv_number, invoice_amount, paid_amount, row, PaymentStatus.COMPLETED.value,
                          PaymentMethod.ONLINE_BANKING.value, source_txn_number)
            _publish_online_banking_mailer_events(payment_lines, paid_amount)

        elif settlement_type == RecordType.EFTP.value:
            # Find the payment using receipt_number and mark it as COMPLETED
            payment: PaymentModel = db.session.query(PaymentModel).filter(
                PaymentModel.receipt_number == source_txn_number).one_or_none()
            payment.payment_status_code = PaymentStatus.COMPLETED.value

        db.session.commit()


def _save_payment(payment_date, inv_number, invoice_amount,  # pylint: disable=too-many-arguments
                  paid_amount, row, status, payment_method, receipt_number):
    # pylint: disable=import-outside-toplevel
    from pay_api.factory.payment_system_factory import PaymentSystemFactory

    payment_account = _get_payment_account(row)
    pay_service = PaymentSystemFactory.create_from_payment_method(payment_method)
    # If status is failed, which means NSF. We already have a COMPLETED payment record, find and update iit.
    payment: PaymentModel = None
    if status == PaymentStatus.FAILED.value:
        payment = _get_payment_by_inv_number_and_status(inv_number, PaymentStatus.COMPLETED.value)
        # Just to handle duplicate rows in settlement file,
        # pull out failed payment record if it exists and no COMPLETED payments are present.
        if not payment:
            # Select the latest failure.
            payment = _get_failed_payment_by_inv_number(inv_number)
    elif status == PaymentStatus.COMPLETED.value:
        # if the payment status is COMPLETED, then make sure there are
        # no other COMPLETED payment for same invoice_number.If found, return. This is to avoid duplicate entries.
        payment = _get_payment_by_inv_number_and_status(inv_number, PaymentStatus.COMPLETED.value)
        if payment:
            return

    if not payment:
        payment = PaymentModel()
    payment.payment_method_code = pay_service.get_payment_method_code()
    payment.payment_status_code = status
    payment.payment_system_code = pay_service.get_payment_system_code()
    payment.invoice_number = inv_number
    payment.invoice_amount = invoice_amount
    payment.payment_account_id = payment_account.id
    payment.payment_date = payment_date
    payment.paid_amount = paid_amount
    payment.receipt_number = receipt_number
    db.session.add(payment)


def _get_failed_payment_by_inv_number(inv_number: str) -> PaymentModel:
    """Get the failed payment record for the invoice number."""
    payment: PaymentModel = db.session.query(PaymentModel) \
        .filter(PaymentModel.invoice_number == inv_number,
                PaymentModel.payment_status_code == PaymentStatus.FAILED.value) \
        .order_by(PaymentModel.payment_date.desc()).first()
    return payment


def _get_payment_by_inv_number_and_status(inv_number: str, status: str) -> PaymentModel:
    """Get payment by invoice number and status."""
    # It's possible to look up null inv_number and return more than one.
    if inv_number is None:
        return None
    payment: PaymentModel = db.session.query(PaymentModel) \
        .filter(PaymentModel.invoice_number == inv_number,
                PaymentModel.payment_status_code == status) \
        .one_or_none()
    return payment


def reconcile_payments(ce):
    """Read the file and update payment details.

    1: Check to see if file has been processed already.
    2: Parse the file and create a dict per row for easy access.
    3: If the transaction is for invoice,
    3.1 : If transaction status is PAID, update invoice and payment statuses, publish to account mailer.
        For Online Banking invoices, publish message to the payment queue.
    3.2 : If transaction status is NOT PAID, update payment status, publish to account mailer and events to handle NSF.
    3.3 : If transaction status is PARTIAL, update payment and invoice status, publish to account mailer.
    4: If the transaction is On Account for Credit, apply the credit to the account.
    """
    msg = ce.data
    file_name: str = msg.get('fileName')
    minio_location: str = msg.get('location')

    cas_settlement: CasSettlementModel = db.session.query(CasSettlementModel) \
        .filter(CasSettlementModel.file_name == file_name).one_or_none()
    if cas_settlement:
        current_app.logger.info('File: %s has been processed or processing in progress. Skipping file. '
                                'Removing this row will allow processing to be restarted.', file_name)
        return
    current_app.logger.info('Creating cas_settlement record for file: %s', file_name)
    cas_settlement = _create_cas_settlement(file_name)

    file = get_object(minio_location, file_name)
    content = file.data.decode('utf-8-sig')

    error_messages = []
    has_errors, error_messages = _process_file_content(content, cas_settlement, msg, error_messages)

    if has_errors and not current_app.config.get('DISABLE_CSV_ERROR_EMAIL'):
        _send_error_email(file_name, minio_location, error_messages, ce, cas_settlement.__tablename__)


def _process_file_content(content: str, cas_settlement: CasSettlementModel,
                          msg: Dict[str, any], error_messages: List[Dict[str, any]]):
    """Process the content of the feedback file."""
    has_errors = False
    # Iterate the rows and create key value pair for each row
    for row in csv.DictReader(content.splitlines()):
        # Convert lower case keys to avoid any key mismatch
        row = dict((k.lower(), v) for k, v in row.items())
        current_app.logger.debug('Processing %s', row)

        # IF not PAD and application amount is zero, continue
        record_type = _get_row_value(row, Column.RECORD_TYPE)
        pad_record_types: Tuple[str] = (RecordType.PAD.value, RecordType.PADR.value, RecordType.PAYR.value)
        if float(_get_row_value(row, Column.APP_AMOUNT)) == 0 and record_type not in pad_record_types:
            continue

        # If PAD, lookup the payment table and mark status based on the payment status
        # If BCOL, lookup the invoices and set the status:
        # Create payment record by looking the receipt_number
        # If EFT/WIRE, lookup the invoices and set the status:
        # Create payment record by looking the receipt_number
        # PS : Duplicating some code to make the code more readable.
        if record_type in pad_record_types:
            # Handle invoices
            has_errors = _process_consolidated_invoices(row, error_messages) or has_errors
        elif record_type in (RecordType.BOLP.value, RecordType.EFTP.value):
            # EFT, WIRE and Online Banking are one-to-one invoice. So handle them in same way.
            has_errors = _process_unconsolidated_invoices(row, error_messages) or has_errors
        elif record_type in (RecordType.ONAC.value, RecordType.CMAP.value, RecordType.DRWP.value):
            has_errors = _process_credit_on_invoices(row, error_messages) or has_errors
        elif record_type == RecordType.ADJS.value:
            current_app.logger.info('Adjustment received for %s.', msg)
        else:
            # For any other transactions like DM log error and continue.
            error_msg = f'Record Type is received as {record_type}, and cannot process {msg}.'
            has_errors = True
            _csv_error_handling(row, error_msg, error_messages)
            # Continue processing

        # Commit the transaction and process next row.
        db.session.commit()

    # Create payment records for lines other than PAD
    try:
        _create_payment_records(content)
    except Exception as e: # NOQA # pylint: disable=broad-except
        error_msg = f'Error creating payment records: {str(e)}'
        has_errors = True
        _csv_error_handling('N/A', error_msg, error_messages, e)
        return has_errors, error_messages

    # Create Credit Records.
    try:
        _create_credit_records(content)
    except Exception as e: # NOQA # pylint: disable=broad-except
        error_msg = f'Error creating credit records: {str(e)}'
        has_errors = True
        _csv_error_handling('N/A', error_msg, error_messages, e)
        return has_errors, error_messages

    # Sync credit memo and on account credits with CFS
    try:
        _sync_credit_records()
    except Exception as e: # NOQA # pylint: disable=broad-except
        error_msg = f'Error syncing credit records: {str(e)}'
        has_errors = True
        _csv_error_handling('N/A', error_msg, error_messages, e)
        return has_errors, error_messages

    cas_settlement.processed_on = datetime.now()
    cas_settlement.save()
    return has_errors, error_messages


def _send_error_email(file_name: str, minio_location: str,  # pylint:disable=too-many-locals
                      error_messages: List[Dict[str, any]],
                      ce, table_name: str):
    """Send the email asynchronously, using the given details."""
    subject = 'Payment Reconciliation Failure'
    token = get_token()
    recipient = current_app.config.get('IT_OPS_EMAIL')
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

    template = env.get_template('payment_reconciliation_failed_email.html')

    params = {
        'fileName': file_name,
        'errorMessages': error_messages,
        'minioLocation': minio_location,
        'payload': json.dumps(dataclasses.asdict(ce)),
        'tableName': table_name
    }
    html_body = template.render(params)
    notify_url = current_app.config.get('NOTIFY_API_ENDPOINT') + 'notify/'
    notify_body = {
        'recipients': recipient,
        'content': {
            'subject': subject,
            'body': html_body
        }
    }
    notify_response = OAuthService.post(notify_url, token=token,
                                        auth_header_type=AuthHeaderType.BEARER,
                                        content_type=ContentType.JSON, data=notify_body)
    current_app.logger.info(f'_send_error_email to recipients: {notify_url}, {recipient}')
    if notify_response:
        response_json = json.loads(notify_response.text)
        if response_json.get('notifyStatus', 'FAILURE') != 'FAILURE':
            current_app.logger.info('_send_error_email notify_response')
        else:
            current_app.logger.info('_send_error_email failed')


def _process_consolidated_invoices(row, error_messages: List[Dict[str, any]]) -> bool:
    has_errors = False
    target_txn_status = _get_row_value(row, Column.TARGET_TXN_STATUS)
    if (target_txn := _get_row_value(row, Column.TARGET_TXN)) == TargetTransaction.INV.value:
        inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
        record_type = _get_row_value(row, Column.RECORD_TYPE)
        current_app.logger.debug('Processing invoice :  %s', inv_number)

        inv_references = _find_invoice_reference_by_number_and_status(inv_number, InvoiceReferenceStatus.ACTIVE.value)

        payment_account: PaymentAccountModel = _get_payment_account(row)

        if target_txn_status.lower() == Status.PAID.value.lower():
            current_app.logger.debug('Fully PAID payment.')
            # if no inv reference is found, and if there are no COMPLETED inv ref, raise alert
            completed_inv_references = _find_invoice_reference_by_number_and_status(
                inv_number, InvoiceReferenceStatus.COMPLETED.value
            )

            if not inv_references and not completed_inv_references:
                error_msg = f'No invoice found for {inv_number} in the system, and cannot process {row}.'
                has_errors = True
                _csv_error_handling(row, error_msg, error_messages)
                return has_errors
            _process_paid_invoices(inv_references, row)
        elif target_txn_status.lower() == Status.NOT_PAID.value.lower() \
                or record_type in (RecordType.PADR.value, RecordType.PAYR.value):
            current_app.logger.info('NOT PAID. NSF identified.')
            # NSF Condition. Publish to account events for NSF.
            if _process_failed_payments(row):
                # Send mailer and account events to update status and send email notification
                _publish_account_events(QueueMessageTypes.NSF_LOCK_ACCOUNT.value, payment_account, row)
        else:
            error_msg = f'Target Transaction Type is received as {target_txn} for PAD, and cannot process {row}.'
            has_errors = True
            _csv_error_handling(row, error_msg, error_messages)
    return has_errors


def _find_invoice_reference_by_number_and_status(inv_number: str, status: str):
    inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
        filter(InvoiceReferenceModel.status_code == status). \
        filter(InvoiceReferenceModel.invoice_number == inv_number). \
        all()
    return inv_references


def _process_unconsolidated_invoices(row, error_messages: List[Dict[str, any]]) -> bool:
    has_errors = False
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
            current_app.logger.info('Found %s completed invoice references for invoice number %s',
                                    len(completed_inv_references), inv_number)
            if len(completed_inv_references) != 1:
                error_msg = (f'More than one or none invoice reference '
                             f'received for invoice number {inv_number} for {record_type}')
                has_errors = True
                _csv_error_handling(row, error_msg, error_messages)
        else:
            # Handle fully PAID and Partially Paid scenarios.
            if target_txn_status.lower() == Status.PAID.value.lower():
                current_app.logger.debug('Fully PAID payment.')
                _process_paid_invoices(inv_references, row)
            elif target_txn_status.lower() == Status.PARTIAL.value.lower():
                current_app.logger.info('Partially PAID.')
                # As per validation above, get first and only inv ref
                _process_partial_paid_invoices(inv_references[0], row)
            else:
                error_msg = (f'Target Transaction Type is received '
                             f'as {target_txn} for {record_type}, and cannot process.')
                has_errors = True
                _csv_error_handling(row, error_msg, error_messages)

    return has_errors


def _csv_error_handling(row, error_msg: str, error_messages: List[Dict[str, any]],
                        ex: Exception = None):
    if ex:
        formatted_traceback = ''.join(traceback.TracebackException.from_exception(ex).format())
        error_msg = f'{error_msg}\n{formatted_traceback}'
    current_app.logger.error(error_msg)
    capture_message(error_msg, level='error')
    error_messages.append({'error': error_msg, 'row': row})


def _process_credit_on_invoices(row, error_messages: List[Dict[str, any]]) -> bool:
    has_errors = False
    # Credit memo can happen for any type of accounts.
    target_txn_status = _get_row_value(row, Column.TARGET_TXN_STATUS)
    if _get_row_value(row, Column.TARGET_TXN) == TargetTransaction.INV.value:
        inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
        current_app.logger.debug('Processing invoice :  %s', inv_number)

        inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
            filter(InvoiceReferenceModel.status_code == InvoiceReferenceStatus.ACTIVE.value). \
            filter(InvoiceReferenceModel.invoice_number == inv_number). \
            all()

        if target_txn_status.lower() == Status.PAID.value.lower():
            current_app.logger.debug('Fully PAID payment.')
            _process_paid_invoices(inv_references, row)
        elif target_txn_status.lower() == Status.PARTIAL.value.lower():
            current_app.logger.info('Partially PAID using credit memo. '
                                    'Ignoring as the credit memo payment is already captured.')
        else:
            error_msg = f'Target Transaction status is received as {target_txn_status} for CMAP, and cannot process.'
            has_errors = True
            _csv_error_handling(row, error_msg, error_messages)
    return has_errors


def _process_paid_invoices(inv_references, row):
    """Process PAID invoices.

    Update invoices as PAID
    Update payment as COMPLETED
    Update invoice_reference as COMPLETED
    Update payment_transaction as COMPLETED.
    """
    for inv_ref in inv_references:
        invoice: InvoiceModel = InvoiceModel.find_by_id(inv_ref.invoice_id)
        if invoice.payment_method_code == PaymentMethod.CC.value:
            current_app.logger.info('Cannot mark CC invoices as PAID.')
            return

    receipt_date: datetime = datetime.strptime(_get_row_value(row, Column.APP_DATE), '%d-%b-%y')
    receipt_number: str = _get_row_value(row, Column.SOURCE_TXN_NO)
    for inv_ref in inv_references:
        inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
        # Find invoice, update status
        inv: InvoiceModel = InvoiceModel.find_by_id(inv_ref.invoice_id)
        _validate_account(inv, row)
        current_app.logger.debug('PAID Invoice. Invoice Reference ID : %s, invoice ID : %s',
                                 inv_ref.id, inv_ref.invoice_id)

        inv.invoice_status_code = InvoiceStatus.PAID.value
        inv.payment_date = receipt_date
        inv.paid = inv.total
        # Create Receipt records
        receipt: ReceiptModel = ReceiptModel()
        receipt.receipt_date = receipt_date
        receipt.receipt_amount = inv.total
        receipt.invoice_id = inv.id
        receipt.receipt_number = receipt_number
        db.session.add(receipt)
        # Publish to the queue if it's an Online Banking payment
        if inv.payment_method_code == PaymentMethod.ONLINE_BANKING.value:
            current_app.logger.debug('Publishing payment event for OB. Invoice : %s', inv.id)
            _publish_payment_event(inv)


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
    current_app.logger.debug('Partial Invoice. Invoice Reference ID : %s, invoice ID : %s',
                             inv_ref.id, inv_ref.invoice_id)
    inv.invoice_status_code = InvoiceStatus.PARTIAL.value
    inv.paid = inv.total - Decimal(_get_row_value(row, Column.TARGET_TXN_OUTSTANDING))
    # Create Receipt records
    receipt: ReceiptModel = ReceiptModel()
    receipt.receipt_date = receipt_date
    receipt.receipt_amount = float(_get_row_value(row, Column.APP_AMOUNT))
    receipt.invoice_id = inv.id
    receipt.receipt_number = receipt_number
    db.session.add(receipt)


def _process_failed_payments(row):
    """Handle failed payments."""
    # 1. Check if there is an NSF record for this account, if there isn't, proceed.
    # 2. SET cfs_account status to FREEZE.
    # 3. Call CFS API to stop further PAD on this account.
    # 4. Reverse the invoice_reference status to ACTIVE, invoice status to SETTLEMENT_SCHED, and delete receipt.
    # 5. Create an NSF invoice for this account.
    # 6. Create invoice reference for the newly created NSF invoice.
    # 7. Adjust invoice in CFS to include NSF fees.
    inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
    payment_account: PaymentAccountModel = _get_payment_account(row)

    # If there is a FAILED payment record for this; it means it's a duplicate event. Ignore it.
    payment: PaymentModel = PaymentModel.find_payment_by_invoice_number_and_status(
        inv_number, PaymentStatus.FAILED.value
    )
    if payment:
        current_app.logger.info('Ignoring duplicate NSF message for invoice : %s ', inv_number)
        return False
    # If there is an NSF row, it means it's a duplicate NSF event. Ignore it.
    if NonSufficientFundsService.exists_for_invoice_number(inv_number):
        current_app.logger.info('Ignoring duplicate NSF event for account: %s ', payment_account.auth_account_id)
        return False

    # Set CFS Account Status.
    cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.PAD.value)
    is_already_frozen = cfs_account.status == CfsAccountStatus.FREEZE.value
    current_app.logger.info('setting payment account id : %s status as FREEZE', payment_account.id)
    cfs_account.status = CfsAccountStatus.FREEZE.value
    payment_account.has_nsf_invoices = datetime.now(tz=timezone.utc)
    # Call CFS to stop any further PAD transactions on this account.
    CFSService.update_site_receipt_method(cfs_account, receipt_method=RECEIPT_METHOD_PAD_STOP)
    if is_already_frozen:
        current_app.logger.info('Ignoring NSF message for invoice : %s as the account is already FREEZE', inv_number)
        return False
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
        invoice.paid = 0

    # Create an invoice for NSF for this account
    reason_description = _get_row_value(row, Column.REVERSAL_REASON_DESC)
    invoice = _create_nsf_invoice(cfs_account, inv_number, payment_account, reason_description)
    # Adjust CFS invoice
    CFSService.add_nsf_adjustment(cfs_account=cfs_account, inv_number=inv_number, amount=invoice.total)
    return True


def _create_credit_records(csv_content: str):
    """Create credit records and sync them up with CFS."""
    # Iterate the rows and store any ONAC RECEIPTs to credit table .
    for row in csv.DictReader(csv_content.splitlines()):
        # Convert lower case keys to avoid any key mismatch
        row = dict((k.lower(), v) for k, v in row.items())
        if _get_row_value(row, Column.TARGET_TXN) == TargetTransaction.RECEIPT.value:
            receipt_number = _get_row_value(row, Column.SOURCE_TXN_NO)
            pay_account = _get_payment_account(row)
            # Create credit if a record doesn't exists for this receipt number.
            if not CreditModel.find_by_cfs_identifier(cfs_identifier=receipt_number):
                CreditModel(
                    cfs_identifier=receipt_number,
                    is_credit_memo=False,
                    amount=float(_get_row_value(row, Column.TARGET_TXN_ORIGINAL)),
                    remaining_amount=float(_get_row_value(row, Column.TARGET_TXN_ORIGINAL)),
                    account_id=pay_account.id
                ).save()


def _check_cfs_accounts_for_pad_and_ob(credit):
    """Ensure we don't have PAD and OB for the same account, because there is no association between CFS and CREDITS."""
    has_pad = False
    has_online_banking = False
    for cfs_account in CfsAccountModel.find_by_account_id(credit.account_id):
        if cfs_account.payment_method == PaymentMethod.PAD.value:
            has_pad = True
        if cfs_account.payment_method == PaymentMethod.ONLINE_BANKING.value:
            has_online_banking = True
    if has_pad and has_online_banking:
        raise Exception(  # pylint: disable=broad-exception-raised
            'Multiple payment methods for the same account for CREDITS'
            ' credits has no link to CFS account.')


def _sync_credit_records():
    """Sync credit records with CFS."""
    # 1. Get all credit records with balance > 0
    # 2. If it's on account receipt call receipt endpoint and calculate balance.
    # 3. If it's credit memo, call credit memo endpoint and calculate balance.
    # 4. Roll up the credits to credit field in payment_account.
    active_credits: List[CreditModel] = db.session.query(CreditModel).filter(CreditModel.remaining_amount > 0).all()
    current_app.logger.info('Found %s credit records', len(active_credits))
    account_ids: List[int] = []
    for credit in active_credits:
        _check_cfs_accounts_for_pad_and_ob(credit)
        cfs_account = CfsAccountModel.find_effective_or_latest_by_payment_method(credit.account_id,
                                                                                 PaymentMethod.PAD.value) \
            or CfsAccountModel.find_effective_or_latest_by_payment_method(credit.account_id,
                                                                          PaymentMethod.ONLINE_BANKING.value)
        account_ids.append(credit.account_id)
        if credit.is_credit_memo:
            credit_memo = CFSService.get_cms(
                cfs_account=cfs_account, cms_number=credit.cfs_identifier)
            credit.remaining_amount = abs(float(credit_memo.get('amount_due')))
        else:
            receipt = CFSService.get_receipt(
                cfs_account=cfs_account, receipt_number=credit.cfs_identifier)
            receipt_amount = float(receipt.get('receipt_amount'))
            applied_amount: float = 0
            for invoice in receipt.get('invoices', []):
                applied_amount += float(invoice.get('amount_applied'))
            credit.remaining_amount = receipt_amount - applied_amount

        credit.save()

    # Roll up the credits and add up to credit in payment_account.
    for account_id in set(account_ids):
        account_credits: List[CreditModel] = db.session.query(CreditModel).filter(
            CreditModel.remaining_amount > 0).filter(CreditModel.account_id == account_id).all()
        credit_total: float = 0
        for account_credit in account_credits:
            credit_total += account_credit.remaining_amount
        pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(account_id)
        pay_account.credit = credit_total
        pay_account.save()


def _get_payment_account(row) -> PaymentAccountModel:
    account_number: str = _get_row_value(row, Column.CUSTOMER_ACC)
    payment_accounts: PaymentAccountModel = db.session.query(PaymentAccountModel) \
        .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
        .filter(CfsAccountModel.cfs_account == account_number) \
        .filter(
        CfsAccountModel.status.in_(
            [CfsAccountStatus.ACTIVE.value, CfsAccountStatus.FREEZE.value, CfsAccountStatus.INACTIVE.value]
        )).all()
    if not all(payment_account.id == payment_accounts[0].id for payment_account in payment_accounts):
        raise Exception('Multiple unique payment accounts for cfs_account.')  # pylint: disable=broad-exception-raised
    return payment_accounts[0] if payment_accounts else None


def _validate_account(inv: InvoiceModel, row: Dict[str, str]):
    """Validate any mismatch in account number."""
    # This should never happen, just in case
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(inv.cfs_account_id)
    if (account_number := _get_row_value(row, Column.CUSTOMER_ACC)) != cfs_account.cfs_account:
        current_app.logger.error('Customer Account received as %s, but expected %s.',
                                 account_number, cfs_account.cfs_account)
        capture_message(f'Customer Account received as {account_number}, but expected {cfs_account.cfs_account}.',
                        level='error')

        raise Exception('Invalid Account Number')  # pylint: disable=broad-exception-raised


def _publish_payment_event(inv: InvoiceModel):
    """Publish payment message to the queue."""
    payload = PaymentTransactionService.create_event_payload(invoice=inv,
                                                             status_code=PaymentStatus.COMPLETED.value)
    try:
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_QUEUE.value,
                message_type=QueueMessageTypes.PAYMENT.value,
                payload=payload,
                topic=get_topic_for_corp_type(inv.corp_type_code)
            )
        )
    except Exception as e:  # NOQA pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Payment Event - %s', payload)
        capture_message(f'Notification to Queue failed for the Payment Event {payload}.',
                        level='error')


def _publish_mailer_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(pay_account, row)
    try:
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_QUEUE.value,
                message_type=message_type,
                payload=payload,
                topic=current_app.config.get('ACCOUNT_MAILER_TOPIC')
            )
        )
    except Exception as e:  # NOQA pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account Mailer %s - %s',
                                   pay_account.auth_account_id, payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')


def _publish_online_banking_mailer_events(rows: List[Dict[str, str]], paid_amount: float):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    pay_account = _get_payment_account(rows[0])  # All rows are for same account.
    # Check for credit, or fully paid or under paid payment
    credit_rows = list(
        filter(lambda r: (_get_row_value(r, Column.TARGET_TXN) == TargetTransaction.RECEIPT.value), rows))
    under_pay_rows = list(
        filter(lambda r: (_get_row_value(r, Column.TARGET_TXN_STATUS).lower() == Status.PARTIAL.value.lower()), rows))

    credit_amount: float = 0
    if credit_rows:
        message_type = QueueMessageTypes.ONLINE_BANKING_OVER_PAYMENT.value
        for row in credit_rows:
            credit_amount += float(_get_row_value(row, Column.APP_AMOUNT))
    elif under_pay_rows:
        message_type = QueueMessageTypes.ONLINE_BANKING_UNDER_PAYMENT.value
    else:
        message_type = QueueMessageTypes.ONLINE_BANKING_PAYMENT.value

    payload = {
        'accountId': pay_account.auth_account_id,
        'paymentMethod': PaymentMethod.ONLINE_BANKING.value,
        'amount': '{:.2f}'.format(paid_amount),  # pylint: disable = consider-using-f-string
        'creditAmount': '{:.2f}'.format(credit_amount)  # pylint: disable = consider-using-f-string
    }

    try:
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_QUEUE.value,
                message_type=message_type,
                payload=payload,
                topic=current_app.config.get('ACCOUNT_MAILER_TOPIC')
            )
        )
    except Exception as e:  # NOQA pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account Mailer %s - %s',
                                   pay_account.auth_account_id, payload)
        capture_message('Notification to Queue failed for the Account Mailer '
                        '{auth_account_id}, {msg}.'.format(auth_account_id=pay_account.auth_account_id, msg=payload),
                        level='error')


def _publish_account_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(pay_account, row)
    try:
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_QUEUE.value,
                message_type=message_type,
                payload=payload,
                topic=current_app.config.get('AUTH_EVENT_TOPIC')
            )
        )
    except Exception as e:  # NOQA pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account %s - %s', pay_account.auth_account_id,
                                   pay_account.name)
        capture_message('Notification to Queue failed for the Account {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')


def _create_event_payload(pay_account, row):
    return {
        'accountId': pay_account.auth_account_id,
        'paymentMethod': _convert_payment_method(_get_row_value(row, Column.SOURCE_TXN)),
        'outstandingAmount': _get_row_value(row, Column.TARGET_TXN_OUTSTANDING),
        'originalAmount': _get_row_value(row, Column.TARGET_TXN_ORIGINAL),
        'amount': _get_row_value(row, Column.APP_AMOUNT)
    }


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
                        payment_account: PaymentAccountModel, reason_description: str) -> InvoiceModel:
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

    NonSufficientFundsService.save_non_sufficient_funds(invoice_id=invoice.id,
                                                        invoice_number=inv_number,
                                                        cfs_account=cfs_account.cfs_account,
                                                        description=reason_description)

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
        fee_distribution_id=distribution.distribution_code_id if distribution else 1)
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
        if _get_row_value(row, Column.RECORD_TYPE) in \
                (RecordType.BOLP.value, RecordType.EFTP.value, RecordType.PAD.value, RecordType.PADR.value,
                 RecordType.PAYR.value):
            settlement_type = _get_row_value(row, Column.RECORD_TYPE)
            break
    return settlement_type


def _create_cas_settlement(file_name: str) -> CasSettlementModel:
    """Create a CAS settlement entry."""
    cas_settlement = CasSettlementModel()
    cas_settlement.file_name = file_name
    cas_settlement.received_on = datetime.now()
    cas_settlement.save()
    return cas_settlement
