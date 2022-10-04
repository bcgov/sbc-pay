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
"""Payment reconciliation file.

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
import os
from datetime import datetime
from typing import Dict, List, Tuple

from entity_queue_common.service_utils import logger
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


APP_CONFIG = config.get_named_config(os.getenv('DEPLOYMENT_ENV', 'production'))


async def _create_payment_records(csv_content: str):
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
            # publish email event.
            await _publish_online_banking_mailer_events(payment_lines, paid_amount)

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
    payment: PaymentModel = db.session.query(PaymentModel) \
        .filter(PaymentModel.invoice_number == inv_number,
                PaymentModel.payment_status_code == status) \
        .one_or_none()
    return payment


async def reconcile_payments(msg: Dict[str, any]):
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
    file_name: str = msg.get('data').get('fileName')
    minio_location: str = msg.get('data').get('location')

    cas_settlement: CasSettlementModel = db.session.query(CasSettlementModel) \
        .filter(CasSettlementModel.file_name == file_name).one_or_none()
    if cas_settlement and not cas_settlement.processed_on:
        logger.info('File: %s has attempted to be processed before.', file_name)
    elif cas_settlement and cas_settlement.processed_on:
        logger.info('File: %s already processed on: %s. Skipping file.', file_name, cas_settlement.processed_on)
        return
    else:
        logger.info('Creating cas_settlement record for file: %s', file_name)
        cas_settlement = _create_cas_settlement(file_name)

    file = get_object(minio_location, file_name)
    content = file.data.decode('utf-8-sig')
    # Iterate the rows and create key value pair for each row
    for row in csv.DictReader(content.splitlines()):
        # Convert lower case keys to avoid any key mismatch
        row = dict((k.lower(), v) for k, v in row.items())
        logger.debug('Processing %s', row)

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
            await _process_consolidated_invoices(row)
        elif record_type in (RecordType.BOLP.value, RecordType.EFTP.value):
            # EFT, WIRE and Online Banking are one-to-one invoice. So handle them in same way.
            await _process_unconsolidated_invoices(row)
        elif record_type in (RecordType.ONAC.value, RecordType.CMAP.value, RecordType.DRWP.value):
            await _process_credit_on_invoices(row)
        elif record_type == RecordType.ADJS.value:
            logger.info('Adjustment received for %s.', msg)
        else:
            # For any other transactions like DM log error and continue.
            logger.error('Record Type is received as %s, and cannot process %s.', record_type, msg)
            capture_message(f'Record Type is received as {record_type}, and cannot process {msg}.', level='error')
            # Continue processing

        # Commit the transaction and process next row.
        db.session.commit()

    # Create payment records for lines other than PAD
    await _create_payment_records(content)

    # Create Credit Records.
    _create_credit_records(content)
    # Sync credit memo and on account credits with CFS
    _sync_credit_records()

    cas_settlement.processed_on = datetime.now()
    cas_settlement.save()


async def _process_consolidated_invoices(row):
    target_txn_status = _get_row_value(row, Column.TARGET_TXN_STATUS)
    if (target_txn := _get_row_value(row, Column.TARGET_TXN)) == TargetTransaction.INV.value:
        inv_number = _get_row_value(row, Column.TARGET_TXN_NO)
        record_type = _get_row_value(row, Column.RECORD_TYPE)
        logger.debug('Processing invoice :  %s', inv_number)

        inv_references = _find_invoice_reference_by_number_and_status(inv_number, InvoiceReferenceStatus.ACTIVE.value)

        payment_account: PaymentAccountModel = _get_payment_account(row)

        if target_txn_status.lower() == Status.PAID.value.lower():
            logger.debug('Fully PAID payment.')
            # if no inv reference is found, and if there are no COMPLETED inv ref, raise alert
            completed_inv_references = _find_invoice_reference_by_number_and_status(
                inv_number, InvoiceReferenceStatus.COMPLETED.value
            )

            if not inv_references and not completed_inv_references:
                logger.error('No invoice found for %s in the system, and cannot process %s.', inv_number, row)
                capture_message(f'No invoice found for {inv_number} in the system, and cannot process {row}.',
                                level='error')
                return
            await _process_paid_invoices(inv_references, row)
            if not APP_CONFIG.DISABLE_PAD_SUCCESS_EMAIL:
                await _publish_mailer_events('PAD.PaymentSuccess', payment_account, row)
        elif target_txn_status.lower() == Status.NOT_PAID.value.lower() \
                or record_type in (RecordType.PADR.value, RecordType.PAYR.value):
            logger.info('NOT PAID. NSF identified.')
            # NSF Condition. Publish to account events for NSF.
            if _process_failed_payments(row):
                # Send mailer and account events to update status and send email notification
                await _publish_account_events('lockAccount', payment_account, row)
        else:
            logger.error('Target Transaction Type is received as %s for PAD, and cannot process %s.', target_txn, row)
            capture_message(
                f'Target Transaction Type is received as {target_txn} for PAD, and cannot process.', level='error')


def _find_invoice_reference_by_number_and_status(inv_number: str, status: str):
    inv_references: List[InvoiceReferenceModel] = db.session.query(InvoiceReferenceModel). \
        filter(InvoiceReferenceModel.status_code == status). \
        filter(InvoiceReferenceModel.invoice_number == inv_number). \
        all()
    return inv_references


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
                    f'More than one or none invoice reference received for invoice number {inv_number} for '
                    f'{record_type}', level='error')
        else:
            # Handle fully PAID and Partially Paid scenarios.
            if target_txn_status.lower() == Status.PAID.value.lower():
                logger.debug('Fully PAID payment.')
                await _process_paid_invoices(inv_references, row)
            elif target_txn_status.lower() == Status.PARTIAL.value.lower():
                logger.info('Partially PAID.')
                # As per validation above, get first and only inv ref
                _process_partial_paid_invoices(inv_references[0], row)
            else:
                logger.error('Target Transaction Type is received as %s for %s, and cannot process.',
                             target_txn, record_type)
                capture_message(
                    f'Target Transaction Type is received as {target_txn} for {record_type}, and cannot process.',
                    level='error')


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
                f'Target Transaction status is received as {target_txn_status} for CMAP, and cannot process.',
                level='error')


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
        if inv.payment_method_code == PaymentMethod.ONLINE_BANKING.value:
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
    # If there is a FAILED payment record for this; it means it's a duplicate event. Ignore it.
    payment: PaymentModel = PaymentModel.find_payment_by_invoice_number_and_status(
        inv_number, PaymentStatus.FAILED.value
    )
    if payment:
        logger.info('Ignoring duplicate NSF message for invoice : %s ', inv_number)
        return False

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
        invoice.paid = 0

    # Create an invoice for NSF for this account
    invoice = _create_nsf_invoice(cfs_account, inv_number, payment_account)
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


def _sync_credit_records():
    """Sync credit records with CFS."""
    # 1. Get all credit records with balance > 0
    # 2. If it's on account receipt call receipt endpoint and calculate balance.
    # 3. If it's credit memo, call credit memo endpoint and calculate balance.
    # 4. Roll up the credits to credit field in payment_account.
    active_credits: List[CreditModel] = db.session.query(CreditModel).filter(CreditModel.remaining_amount > 0).all()
    logger.info('Found %s credit records', len(active_credits))
    account_ids: List[int] = []
    for credit in active_credits:
        account_ids.append(credit.account_id)
        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(credit.account_id)
        if credit.is_credit_memo:
            credit_memo = CFSService.get_cms(cfs_account=cfs_account, cms_number=credit.cfs_identifier)
            credit.remaining_amount = abs(float(credit_memo.get('amount_due')))
        else:
            receipt = CFSService.get_receipt(cfs_account=cfs_account, receipt_number=credit.cfs_identifier)
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
    payment_account: PaymentAccountModel = db.session.query(PaymentAccountModel) \
        .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
        .filter(CfsAccountModel.cfs_account == account_number) \
        .filter(
        CfsAccountModel.status.in_(
            [CfsAccountStatus.ACTIVE.value, CfsAccountStatus.FREEZE.value, CfsAccountStatus.INACTIVE.value]
        )).one_or_none()

    return payment_account


def _validate_account(inv: InvoiceModel, row: Dict[str, str]):
    """Validate any mismatch in account number."""
    # This should never happen, just in case
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(inv.cfs_account_id)
    if (account_number := _get_row_value(row, Column.CUSTOMER_ACC)) != cfs_account.cfs_account:
        logger.error('Customer Account received as %s, but expected %s.', account_number, cfs_account.cfs_account)
        capture_message(f'Customer Account received as {account_number}, but expected {cfs_account.cfs_account}.',
                        level='error')

        raise Exception('Invalid Account Number')


async def _publish_payment_event(inv: InvoiceModel):
    """Publish payment message to the queue."""
    payment_event_payload = PaymentTransactionService.create_event_payload(invoice=inv,
                                                                           status_code=PaymentStatus.COMPLETED.value)
    try:

        await publish(payload=payment_event_payload, client_name=APP_CONFIG.NATS_PAYMENT_CLIENT_NAME,
                      subject=get_pay_subject_name(inv.corp_type_code, subject_format=APP_CONFIG.NATS_PAYMENT_SUBJECT))
    except Exception as e:  # NOQA pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Payment Event - %s', payment_event_payload)
        capture_message(f'Notification to Queue failed for the Payment Event {payment_event_payload}.',
                        level='error')


async def _publish_mailer_events(message_type: str, pay_account: PaymentAccountModel, row: Dict[str, str]):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    payload = _create_event_payload(message_type, pay_account, row)
    try:
        await publish(payload=payload,
                      client_name=APP_CONFIG.NATS_MAILER_CLIENT_NAME,
                      subject=APP_CONFIG.NATS_MAILER_SUBJECT)
    except Exception as e:  # NOQA pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Account Mailer %s - %s', pay_account.auth_account_id,
                       payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')


async def _publish_online_banking_mailer_events(rows: List[Dict[str, str]], paid_amount: float):
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
        message_type = 'bc.registry.payment.OverPaid'
        for row in credit_rows:
            credit_amount += float(_get_row_value(row, Column.APP_AMOUNT))
    elif under_pay_rows:
        message_type = 'bc.registry.payment.UnderPaid'
    else:
        message_type = 'bc.registry.payment.Payment'

    queue_data = {
        'accountId': pay_account.auth_account_id,
        'paymentMethod': PaymentMethod.ONLINE_BANKING.value,
        'amount': '{:.2f}'.format(paid_amount),  # pylint: disable = consider-using-f-string
        'creditAmount': '{:.2f}'.format(credit_amount)  # pylint: disable = consider-using-f-string
    }

    payload = {
        'specversion': '1.x-wip',
        'type': message_type,
        'source': f'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/{pay_account.auth_account_id}',
        'id': f'{pay_account.auth_account_id}',
        'time': f'{datetime.now()}',
        'datacontenttype': 'application/json',
        'data': queue_data
    }

    try:
        await publish(payload=payload,
                      client_name=APP_CONFIG.NATS_MAILER_CLIENT_NAME,
                      subject=APP_CONFIG.NATS_MAILER_SUBJECT)
    except Exception as e:  # NOQA pylint: disable=broad-except
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
    except Exception as e:  # NOQA pylint: disable=broad-except
        logger.error(e)
        logger.warning('Notification to Queue failed for the Account %s - %s', pay_account.auth_account_id,
                       pay_account.name)
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


def _create_cas_settlement(file_name: str) -> CasSettlementModel:
    """Create a CAS settlement entry."""
    cas_settlement = CasSettlementModel()
    cas_settlement.file_name = file_name
    cas_settlement.received_on = datetime.now()
    cas_settlement.save()
    return cas_settlement
