# Copyright © 2023 Province of British Columbia
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
"""EFT reconciliation file.

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
from datetime import datetime
from operator import and_
from typing import Dict, List

from _decimal import Decimal
from entity_queue_common.service_utils import logger
from pay_api import db
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.eft_service import EftService as EFTService
from pay_api.services.eft_short_names import EFTShortnames
from pay_api.utils.enums import EFTFileLineType, EFTProcessStatus, InvoiceStatus, PaymentMethod
from sentry_sdk import capture_message

from reconciliations.eft import EFTHeader, EFTRecord, EFTTrailer
from reconciliations.minio import get_object


async def reconcile_eft_payments(msg: Dict[str, any]):  # pylint: disable=too-many-locals
    """Read the TDI17 file, create processing records and update payment details.

    1: Check to see if file has been previously processed.
    2: Create / Update EFT File Model record
    3: Parse EFT header, transactions and trailer
    4: Validate header and trailer - persist any error messages
    4.1: If header and/or trailer is invalid, set FAIL state and return
    5: Validate and persist transaction details - persist any error messages
    5.1: If transaction details are invalid, set FAIL state and return
    6: Calculate total transaction balance per short name - dictionary
    7: Apply balance to outstanding EFT invoices - Update invoice paid amount and status, create payment,
        invoice reference, and receipt
    8: Create EFT Credit records for left over balances
    9: Finalize and complete
    """
    # Fetch EFT File
    file_name: str = msg.get('data').get('fileName')
    minio_location: str = msg.get('data').get('location')
    file = get_object(minio_location, file_name)
    file_content = file.data.decode('utf-8-sig')

    # Split into lines
    lines = file_content.splitlines()

    # Check if there is an existing EFT File record
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

    if eft_file_model and eft_file_model.status_code == EFTProcessStatus.COMPLETED.value:
        logger.info('File: %s already completed processing on %s.', file_name, eft_file_model.completed_on)
        return

    # There is no existing EFT File record - instantiate one
    if eft_file_model is None:
        eft_file_model = EFTFileModel()
        eft_file_model.file_ref = file_name

    # EFT File - In Progress
    eft_file_model.status_code = EFTProcessStatus.IN_PROGRESS.value
    eft_file_model.save()

    # EFT File parsed data holders
    eft_header: EFTHeader = None
    eft_trailer: EFTTrailer = None
    eft_transactions: [EFTRecord] = []

    # Read and parse EFT file header, trailer, transactions
    for index, line in enumerate(lines):
        if index == 0:
            eft_header = EFTHeader(line, index)
        elif index == len(lines) - 1:
            eft_trailer = EFTTrailer(line, index)
        else:
            eft_transactions.append(EFTRecord(line, index))

    eft_header_valid = _process_eft_header(eft_header, eft_file_model)
    eft_trailer_valid = _process_eft_trailer(eft_trailer, eft_file_model)

    # If header and/or trailer has errors do not proceed
    if not (eft_header_valid and eft_trailer_valid):
        logger.error('Failed to process file %s with an invalid header or trailer.', file_name)
        eft_file_model.status_code = EFTProcessStatus.FAILED.value
        eft_file_model.save()
        return

    has_eft_transaction_errors = False

    # Parse EFT Transactions
    for eft_transaction in eft_transactions:
        if eft_transaction.has_errors():  # Flag any instance of an error - will indicate file is partially processed
            has_eft_transaction_errors = True
            _save_eft_transaction(eft_record=eft_transaction, eft_file_model=eft_file_model, is_error=True)
        else:
            # Save TDI17 transaction record
            _save_eft_transaction(eft_record=eft_transaction, eft_file_model=eft_file_model, is_error=False)

    # EFT Transactions have parsing errors - stop and FAIL transactions
    # We want a full file to be parseable as we want to get a full accurate balance before applying them to invoices
    if has_eft_transaction_errors:
        logger.error('Failed to process file %s has transaction parsing errors.', file_name)
        _update_transactions_to_fail(eft_file_model)
        return

    # Generate dictionary with shortnames and total deposits
    shortname_balance = _shortname_balance_as_dict(eft_transactions)

    # Credit short name and map to eft transaction for tracking
    has_eft_credits_error = _process_eft_credits(shortname_balance, eft_file_model.id)

    # Process payments, update invoice and create receipt
    has_eft_transaction_errors = _process_eft_payments(shortname_balance, eft_file_model)

    # Mark EFT File partially processed due to transaction errors
    # Rollback EFT transactions and update to FAIL status
    if has_eft_transaction_errors or has_eft_credits_error:
        db.session.rollback()
        _update_transactions_to_fail(eft_file_model)
        logger.error('Failed to process file %s due to transaction errors.', file_name)
        return

    _finalize_process_state(eft_file_model)


def _finalize_process_state(eft_file_model: EFTFileModel):
    """Set the final transaction and file statuses."""
    _update_transactions_to_complete(eft_file_model)

    status_code = EFTProcessStatus.COMPLETED.value
    eft_file_model.status_code = status_code
    eft_file_model.completed_on = datetime.now()
    eft_file_model.save()


def _process_eft_header(eft_header: EFTHeader, eft_file_model: EFTFileModel) -> bool:
    """Process the EFT Header."""
    if eft_header is None:
        logger.error('Failed to process file %s with an invalid header.', eft_file_model.file_ref)
        return False

    # Populate header and trailer data on EFT File record - values will return None if parsing failed
    _set_eft_header_on_file(eft_header, eft_file_model)

    # Errors on parsing header - create EFT error records
    if eft_header is not None and eft_header.has_errors():
        _save_eft_header_error(eft_header, eft_file_model)
        return False

    return True


def _process_eft_trailer(eft_trailer: EFTTrailer, eft_file_model: EFTFileModel) -> bool:
    """Process the EFT Trailer."""
    if eft_trailer is None:
        logger.error('Failed to process file %s with an invalid trailer.', eft_file_model.file_ref)
        return False

    # Populate header and trailer data on EFT File record - values will return None if parsing failed
    _set_eft_trailer_on_file(eft_trailer, eft_file_model)

    # Errors on parsing trailer - create EFT error records
    if eft_trailer is not None and eft_trailer.has_errors():
        _save_eft_trailer_error(eft_trailer, eft_file_model)
        return False

    return True


def _process_eft_credits(shortname_balance, eft_file_id):
    """Credit shortname for each transaction."""
    has_credit_errors = False
    for shortname in shortname_balance.keys():
        try:
            eft_shortname = _get_shortname(shortname)
            payment_account_id = None

            # Get payment account if short name is mapped to an auth account
            if eft_shortname.auth_account_id is not None:
                payment_account: PaymentAccountModel = PaymentAccountModel.\
                    find_by_auth_account_id(eft_shortname.auth_account_id)
                payment_account_id = payment_account.id

            eft_transactions = shortname_balance[shortname]['transactions']

            for eft_transaction in eft_transactions:
                # Check if there is an existing eft credit for this file and transaction
                eft_credit_model = db.session.query(EFTCreditModel) \
                    .filter(EFTCreditModel.eft_file_id == eft_file_id) \
                    .filter(EFTCreditModel.short_name_id == eft_shortname.id) \
                    .filter(EFTCreditModel.eft_transaction_id == eft_transaction['id']) \
                    .one_or_none()

                if eft_credit_model is None:
                    eft_credit_model = EFTCreditModel()

                # Skip if there is no deposit amount
                deposit_amount = eft_transaction['deposit_amount']
                if not deposit_amount > 0:
                    continue

                eft_credit_model.eft_file_id = eft_file_id
                eft_credit_model.payment_account_id = payment_account_id
                eft_credit_model.short_name_id = eft_shortname.id
                eft_credit_model.amount = deposit_amount
                eft_credit_model.remaining_amount = deposit_amount
                eft_credit_model.eft_transaction_id = eft_transaction['id']
                db.session.add(eft_credit_model)
        except Exception as e:  # NOQA pylint: disable=broad-exception-caught
            has_credit_errors = True
            logger.error(e)
            capture_message('EFT Failed to set EFT balance.', level='error')
    return has_credit_errors


def _process_eft_payments(shortname_balance: Dict, eft_file: EFTFileModel) -> bool:
    """Process payments by creating payment records and updating invoice state."""
    has_eft_transaction_errors = False

    for shortname in shortname_balance.keys():
        # Retrieve or Create shortname mapping
        eft_shortname_model = _get_shortname(shortname)

        # No balance to apply - move to next shortname
        if shortname_balance[shortname]['balance'] <= 0:
            logger.warning('UNEXPECTED BALANCE: %s had zero or less balance on file: %s', shortname, eft_file.file_ref)
            continue

        # check if short name is mapped to an auth account
        if eft_shortname_model is not None and eft_shortname_model.auth_account_id is not None:
            # We have a mapping and can continue processing
            try:
                auth_account_id = eft_shortname_model.auth_account_id
                # Find invoices to be paid
                invoices: List[InvoiceModel] = EFTShortnames.get_invoices_owing(auth_account_id)
                if invoices is not None:
                    for invoice in invoices:
                        _pay_invoice(invoice=invoice,
                                     shortname_balance=shortname_balance[shortname])

            except Exception as e:  # NOQA pylint: disable=broad-exception-caught
                has_eft_transaction_errors = True
                logger.error(e)
                capture_message('EFT Failed to apply balance to invoice.', level='error')

    return has_eft_transaction_errors


def _set_eft_header_on_file(eft_header: EFTHeader, eft_file_model: EFTFileModel):
    """Set EFT Header information on EFTFile model."""
    eft_file_model.file_creation_date = getattr(eft_header, 'creation_datetime', None)
    eft_file_model.deposit_from_date = getattr(eft_header, 'starting_deposit_date', None)
    eft_file_model.deposit_to_date = getattr(eft_header, 'ending_deposit_date', None)


def _set_eft_trailer_on_file(eft_trailer: EFTTrailer, eft_file_model: EFTFileModel):
    """Set EFT Trailer information on EFTFile model."""
    eft_file_model.number_of_details = getattr(eft_trailer, 'number_of_details', None)
    eft_file_model.total_deposit_cents = getattr(eft_trailer, 'total_deposit_amount', None)


def _set_eft_base_error(line_type: str, index: int,
                        eft_file_id: int, error_messages: [str]) -> EFTTransactionModel:
    """Instantiate EFT Transaction model error record."""
    eft_transaction_model = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_id) \
        .filter(EFTTransactionModel.line_type == line_type).one_or_none()

    if eft_transaction_model is None:
        eft_transaction_model = EFTTransactionModel()

    eft_transaction_model.line_type = line_type
    eft_transaction_model.line_number = index
    eft_transaction_model.file_id = eft_file_id
    eft_transaction_model.status_code = EFTProcessStatus.FAILED.value
    eft_transaction_model.error_messages = error_messages

    return eft_transaction_model


def _save_eft_header_error(eft_header: EFTHeader, eft_file_model: EFTFileModel):
    """Save or update EFT Header error record."""
    eft_transaction_model = _set_eft_base_error(line_type=EFTFileLineType.HEADER.value,
                                                index=eft_header.index,
                                                eft_file_id=eft_file_model.id,
                                                error_messages=eft_header.get_error_messages())
    eft_transaction_model.save()


def _save_eft_trailer_error(eft_trailer: EFTTrailer, eft_file_model: EFTFileModel):
    """Save or update EFT Trailer error record."""
    eft_transaction_model = _set_eft_base_error(line_type=EFTFileLineType.TRAILER.value,
                                                index=eft_trailer.index,
                                                eft_file_id=eft_file_model.id,
                                                error_messages=eft_trailer.get_error_messages())
    eft_transaction_model.save()


def _save_eft_transaction(eft_record: EFTRecord, eft_file_model: EFTFileModel, is_error: bool):
    """Save or update EFT Transaction details record."""
    line_type = EFTFileLineType.TRANSACTION.value
    status_code = EFTProcessStatus.FAILED.value if is_error else EFTProcessStatus.IN_PROGRESS.value

    eft_transaction_model = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_number == eft_record.index) \
        .filter(EFTTransactionModel.line_type == line_type).one_or_none()

    if eft_transaction_model is None:
        eft_transaction_model = EFTTransactionModel()

    if eft_record.transaction_description:
        eft_short_name: EFTShortnameModel = _get_shortname(eft_record.transaction_description)
        eft_transaction_model.short_name_id = eft_short_name.id if eft_short_name else None

    eft_transaction_model.line_type = line_type
    eft_transaction_model.line_number = eft_record.index
    eft_transaction_model.file_id = eft_file_model.id
    eft_transaction_model.status_code = status_code
    eft_transaction_model.error_messages = eft_record.get_error_messages()
    eft_transaction_model.batch_number = getattr(eft_record, 'batch_number', None)
    eft_transaction_model.sequence_number = getattr(eft_record, 'transaction_sequence', None)
    eft_transaction_model.jv_type = getattr(eft_record, 'jv_type', None)
    eft_transaction_model.jv_number = getattr(eft_record, 'jv_number', None)
    deposit_amount_cad = getattr(eft_record, 'deposit_amount_cad', None)
    eft_transaction_model.deposit_amount_cents = deposit_amount_cad
    eft_transaction_model.save()

    eft_record.id = eft_transaction_model.id


def _update_transactions_to_fail(eft_file_model: EFTFileModel) -> int:
    """Set EFT transactions to fail status."""
    result = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id,
                EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value) \
        .update({EFTTransactionModel.status_code: EFTProcessStatus.FAILED.value}, synchronize_session='fetch')

    eft_file_model.status_code = EFTProcessStatus.FAILED.value
    eft_file_model.save()

    return result


def _update_transactions_to_complete(eft_file_model: EFTFileModel) -> int:
    """Set EFT transactions to complete status if they are currently in progress."""
    result = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.status_code == EFTProcessStatus.IN_PROGRESS.value) \
        .update({EFTTransactionModel.status_code: EFTProcessStatus.COMPLETED.value}, synchronize_session='fetch')
    db.session.commit()

    return result


def _get_shortname(short_name: str) -> EFTShortnameModel:
    """Save short name if it doesn't exist."""
    eft_shortname = db.session.query(EFTShortnameModel) \
        .filter(EFTShortnameModel.short_name == short_name) \
        .one_or_none()

    if eft_shortname is None:
        eft_shortname = EFTShortnameModel()
        eft_shortname.short_name = short_name
        eft_shortname.save()

    return eft_shortname


def _get_invoices_owing(auth_account_id: str) -> [InvoiceModel]:
    """Return invoices that have not been fully paid."""
    unpaid_status = (InvoiceStatus.PARTIAL.value,
                     InvoiceStatus.CREATED.value, InvoiceStatus.OVERDUE.value)
    query = db.session.query(InvoiceModel) \
        .join(PaymentAccountModel, and_(PaymentAccountModel.id == InvoiceModel.payment_account_id,
                                        PaymentAccountModel.auth_account_id == auth_account_id)) \
        .filter(InvoiceModel.invoice_status_code.in_(unpaid_status)) \
        .order_by(InvoiceModel.created_on.asc())

    return query.all()


def _shortname_balance_as_dict(eft_transactions: List[EFTRecord]) -> Dict:
    """Create a dictionary mapping for shortname and total deposits from TDI17 file."""
    shortname_balance = {}

    for eft_transaction in eft_transactions:
        # Skip any transactions with errors
        if eft_transaction.has_errors():
            continue

        shortname = eft_transaction.transaction_description
        transaction_date = eft_transaction.transaction_date
        deposit_amount = eft_transaction.deposit_amount_cad / 100
        transaction = {'id': eft_transaction.id, 'deposit_amount': deposit_amount}

        shortname_balance.setdefault(shortname, {'balance': 0})
        shortname_balance[shortname]['transaction_date'] = transaction_date
        shortname_balance[shortname]['balance'] += deposit_amount
        shortname_balance[shortname].setdefault('transactions', []).append(transaction)

    return shortname_balance


def _pay_invoice(invoice: InvoiceModel, shortname_balance: Dict):
    """Pay for an invoice and update invoice state."""
    payment_date = shortname_balance.get('transaction_date') or datetime.now()
    balance = shortname_balance.get('balance')

    # # Get the unpaid total - could be partial
    unpaid_total = _get_invoice_unpaid_total(invoice)

    # Determine the payable amount based on what is available in the shortname balance
    payable_amount = unpaid_total if balance >= unpaid_total else balance

    # Create the payment record
    eft_payment_service: EFTService = PaymentSystemFactory.create_from_payment_method(PaymentMethod.EFT.value)

    payment, invoice_reference, receipt = eft_payment_service.apply_credit(invoice=invoice,
                                                                           payment_date=payment_date,
                                                                           auto_save=False)

    db.session.add(payment)
    db.session.add(invoice_reference)
    db.session.add(receipt)

    # Paid - update the shortname balance
    shortname_balance['balance'] -= payable_amount


def _get_invoice_unpaid_total(invoice: InvoiceModel) -> Decimal:
    invoice_total = invoice.total or 0
    invoice_paid = invoice.paid or 0

    return invoice_total - invoice_paid
