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
"""EFT reconciliation file."""
from datetime import datetime
from typing import Dict, List

from flask import current_app
from pay_api import db
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.services.eft_short_name_historical import EFTShortnameHistorical as EFTHistoryService
from pay_api.services.eft_short_name_historical import EFTShortnameHistory as EFTHistory
from pay_api.services.eft_short_name_links import EFTShortnameLinks as EFTShortnameLinksService
from pay_api.services.eft_short_names import EFTShortnames as EFTShortnamesService
from pay_api.utils.enums import EFTFileLineType, EFTPaymentActions, EFTProcessStatus, EFTShortnameType

from pay_queue.minio import get_object
from pay_queue.services.eft import EFTHeader, EFTRecord, EFTTrailer
from pay_queue.services.email_service import EmailParams, send_error_email


class EFTReconciliation:  # pylint: disable=too-few-public-methods
    """Initialize the EFTReconciliation."""

    def __init__(self, ce):
        """:param ce: The cloud event object containing relevant data."""
        self.ce = ce
        self.msg = ce.data
        self.file_name: str = self.msg.get("fileName")
        self.minio_location: str = self.msg.get("location")
        self.error_messages: List[Dict[str, any]] = []

    def eft_error_handling(self, row, error_msg: str, capture_error: bool = True, table_name: str = None):
        """Handle EFT errors by logging, capturing messages, and optionally sending an email."""
        if capture_error:
            current_app.logger.error(error_msg, exc_info=True)
        self.error_messages.append({"error": error_msg, "row": row})
        if table_name is not None:
            email_service_params = EmailParams(
                subject="EFT TDI17 Reconciliation Failure",
                file_name=self.file_name,
                minio_location=self.minio_location,
                error_messages=self.error_messages,
                ce=self.ce,
                table_name=table_name,
            )
            send_error_email(email_service_params)


def _validate_configuration(context: EFTReconciliation) -> bool:
    """Validate required configuration is available."""
    is_valid = True
    if current_app.config.get("EFT_TDI17_LOCATION_ID") is None:
        is_valid = False
        context.eft_error_handling("N/A", "Missing EFT_TDI17_LOCATION_ID configuration")
    if not current_app.config.get("EFT_WIRE_PATTERNS"):
        is_valid = False
        context.eft_error_handling("N/A", "Missing EFT_WIRE_PATTERNS configuration")
    if not current_app.config.get("EFT_PATTERNS"):
        is_valid = False
        context.eft_error_handling("N/A", "Missing EFT_PATTERNS configuration")

    return is_valid


def reconcile_eft_payments(ce):  # pylint: disable=too-many-locals
    """Read the TDI17 file, create processing records and update payment details.

    1: Check to see if file has been previously processed.
    2: Create / Update EFT File Model record
    3: Parse EFT header, transactions and trailer
    4: Validate header and trailer - persist any error messages
    4.1: If header and/or trailer is invalid, set FAIL state and return
    5: Validate and persist transaction details - persist any error messages
    5.1: If transaction details are invalid, set FAIL state and return
    6: Calculate total transaction balance per short name - dictionary
    7: Create EFT Credit records for left over balances
    8: Finalize and complete
    """
    context = EFTReconciliation(ce)
    if not _validate_configuration(context):
        return

    # Used to filter transactions by location id to isolate EFT specific transactions from the TDI17
    eft_location_id = current_app.config.get("EFT_TDI17_LOCATION_ID")

    # Fetch EFT File
    file = get_object(context.minio_location, context.file_name)
    file_content = file.data.decode("utf-8-sig")

    # Split into lines
    lines = file_content.splitlines()

    # Check if there is an existing EFT File record
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == context.file_name).one_or_none()
    )

    if eft_file_model and eft_file_model.status_code in [
        EFTProcessStatus.IN_PROGRESS.value,
        EFTProcessStatus.COMPLETED.value,
    ]:
        current_app.logger.info("File: %s already %s.", context.file_name, str(eft_file_model.status_code))
        return

    # There is no existing EFT File record - instantiate one
    if eft_file_model is None:
        eft_file_model = EFTFileModel()
        eft_file_model.file_ref = context.file_name

    # EFT File - In Progress
    eft_file_model.status_code = EFTProcessStatus.IN_PROGRESS.value
    eft_file_model.save()

    eft_header, eft_trailer, eft_transactions = _parse_tdi17_lines(lines)
    eft_header_valid = _process_eft_header(eft_header, eft_file_model)
    eft_trailer_valid = _process_eft_trailer(eft_trailer, eft_file_model)

    # If header and/or trailer has errors do not proceed
    if not (eft_header_valid and eft_trailer_valid):
        error_msg = f"Failed to process file {context.file_name} with an invalid header or trailer."
        eft_file_model.status_code = EFTProcessStatus.FAILED.value
        eft_file_model.save()
        context.eft_error_handling("N/A", error_msg, table_name=eft_file_model.__tablename__)
        return

    has_eft_transaction_errors = False

    # Include only transactions that are eft/wire or has an error - ignore non EFT/Wire
    eft_transactions = _filter_eft_transactions(eft_transactions, eft_location_id)

    # Parse EFT Transactions
    for eft_transaction in eft_transactions:
        if eft_transaction.has_errors():  # Flag any instance of an error - will indicate file is partially processed
            has_eft_transaction_errors = True
            context.eft_error_handling(
                eft_transaction.index,
                eft_transaction.errors[0].message,
                capture_error=False,
            )
            _save_eft_transaction(eft_record=eft_transaction, eft_file_model=eft_file_model, is_error=True)
        else:
            # Save TDI17 transaction record
            _save_eft_transaction(
                eft_record=eft_transaction,
                eft_file_model=eft_file_model,
                is_error=False,
            )

    # EFT Transactions have parsing errors - stop and FAIL transactions
    # We want a full file to be parseable as we want to get a full accurate balance before applying them to invoices
    if has_eft_transaction_errors:
        error_msg = f"Failed to process file {context.file_name} has transaction parsing errors."
        _update_transactions_to_fail(eft_file_model)
        context.eft_error_handling("N/A", error_msg, table_name=eft_file_model.__tablename__)
        return

    # Generate dictionary with shortnames and total deposits
    shortname_balance = _shortname_balance_as_dict(eft_transactions)

    # Credit short name and map to eft transaction for tracking
    has_eft_credits_error = _process_eft_credits(shortname_balance, eft_file_model.id)

    # Rollback EFT transactions and update to FAIL status
    if has_eft_transaction_errors or has_eft_credits_error:
        db.session.rollback()
        _update_transactions_to_fail(eft_file_model)
        error_msg = f"Failed to process file {context.file_name} due to transaction errors."
        context.eft_error_handling("N/A", error_msg, table_name=eft_file_model.__tablename__)
        return

    _finalize_process_state(eft_file_model)

    # Apply EFT Short name link pending payments after finalizing TDI17 processing to allow
    # for it to be committed first
    _apply_eft_pending_payments(context, shortname_balance)


def _parse_tdi17_lines(eft_lines: List[str]):
    """Parse EFT file header, trailer, transactions."""
    eft_header: EFTHeader = None
    eft_trailer: EFTTrailer = None
    eft_transactions: List[EFTRecord] = []
    for index, line in enumerate(eft_lines):
        if index == 0:
            eft_header = EFTHeader(line, index)
        elif index == len(eft_lines) - 1:
            eft_trailer = EFTTrailer(line, index)
        else:
            eft_transactions.append(EFTRecord(line, index))
    return eft_header, eft_trailer, eft_transactions


def _apply_eft_pending_payments(context: EFTReconciliation, shortname_balance):
    """Apply payments to short name links."""
    for shortname in shortname_balance.keys():
        short_name_type = shortname_balance[shortname]["short_name_type"]
        eft_short_name = _get_shortname(shortname, short_name_type)

        # Generated short names will not have auto payments since they will always be created then manually mapped
        # Skip for efficiency
        if eft_short_name.is_generated:
            continue

        eft_credit_balance = EFTCreditModel.get_eft_credit_balance(eft_short_name.id)
        shortname_links = EFTShortnameLinksService.get_shortname_links(eft_short_name.id).get("items", [])

        # Don't apply auto payments for multi link accounts
        if len(shortname_links) > 1:
            continue

        for shortname_link in shortname_links:
            # We are expecting pending payments to have been cleared since this runs after the
            # eft task job. Something may have gone wrong, we will skip this link.
            if shortname_link.get("has_pending_payment"):
                error_msg = f"Unexpected pending payment on link: {shortname_link.id}"
                context.eft_error_handling("N/A", error_msg, table_name=eft_short_name.__tablename__)
                continue

            amount_owing = shortname_link.get("amount_owing")
            auth_account_id = shortname_link.get("account_id")
            if 0 < amount_owing <= eft_credit_balance:
                try:
                    payload = {
                        "action": EFTPaymentActions.APPLY_CREDITS.value,
                        "accountId": auth_account_id,
                    }
                    EFTShortnamesService.process_payment_action(eft_short_name.id, payload)
                except Exception as exception:  # NOQA # pylint: disable=broad-except
                    # EFT Short name service handles commit and rollback when the action fails, we just need to make
                    # sure we log the error here
                    error_msg = "error in _apply_eft_pending_payments."
                    context.eft_error_handling("N/A", error_msg, ex=exception)


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
        current_app.logger.error("Failed to process file %s with an invalid header.", eft_file_model.file_ref)
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
        current_app.logger.error(
            "Failed to process file %s with an invalid trailer.",
            eft_file_model.file_ref,
        )
        return False

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
            short_name_type = shortname_balance[shortname]["short_name_type"]
            eft_short_name = _get_shortname(shortname, short_name_type)
            eft_transactions = shortname_balance[shortname]["transactions"]

            for eft_transaction in eft_transactions:
                # Check if there is an existing eft credit for this file and transaction
                eft_credit_model = (
                    db.session.query(EFTCreditModel)
                    .filter(EFTCreditModel.eft_file_id == eft_file_id)
                    .filter(EFTCreditModel.short_name_id == eft_short_name.id)
                    .filter(EFTCreditModel.eft_transaction_id == eft_transaction["id"])
                    .one_or_none()
                )

                if eft_credit_model is None:
                    eft_credit_model = EFTCreditModel()

                # Skip if there is no deposit amount
                deposit_amount = eft_transaction["deposit_amount"]
                if not deposit_amount > 0:
                    continue

                eft_credit_model.eft_file_id = eft_file_id
                eft_credit_model.short_name_id = eft_short_name.id
                eft_credit_model.amount = deposit_amount
                eft_credit_model.remaining_amount = deposit_amount
                eft_credit_model.eft_transaction_id = eft_transaction["id"]
                eft_credit_model.flush()

                credit_balance = EFTCreditModel.get_eft_credit_balance(eft_credit_model.short_name_id)
                history_transaction_date = eft_transaction.get("deposit_date", None)
                EFTHistoryService.create_funds_received(
                    EFTHistory(
                        short_name_id=eft_credit_model.short_name_id,
                        amount=deposit_amount,
                        credit_balance=credit_balance,
                        transaction_date=history_transaction_date,
                    )
                ).flush()
        except Exception as e:  # NOQA pylint: disable=broad-exception-caught
            has_credit_errors = True
            current_app.logger.error(e, exc_info=True)
    return has_credit_errors


def _set_eft_header_on_file(eft_header: EFTHeader, eft_file_model: EFTFileModel):
    """Set EFT Header information on EFTFile model."""
    eft_file_model.file_creation_date = getattr(eft_header, "creation_datetime", None)
    eft_file_model.deposit_from_date = getattr(eft_header, "starting_deposit_date", None)
    eft_file_model.deposit_to_date = getattr(eft_header, "ending_deposit_date", None)


def _set_eft_base_error(line_type: str, index: int, eft_file_id: int, error_messages: [str]) -> EFTTransactionModel:
    """Instantiate EFT Transaction model error record."""
    eft_transaction_model = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_id)
        .filter(EFTTransactionModel.line_type == line_type)
        .one_or_none()
    )

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
    eft_transaction_model = _set_eft_base_error(
        line_type=EFTFileLineType.HEADER.value,
        index=eft_header.index,
        eft_file_id=eft_file_model.id,
        error_messages=eft_header.get_error_messages(),
    )
    eft_transaction_model.save()


def _save_eft_trailer_error(eft_trailer: EFTTrailer, eft_file_model: EFTFileModel):
    """Save or update EFT Trailer error record."""
    eft_transaction_model = _set_eft_base_error(
        line_type=EFTFileLineType.TRAILER.value,
        index=eft_trailer.index,
        eft_file_id=eft_file_model.id,
        error_messages=eft_trailer.get_error_messages(),
    )
    eft_transaction_model.save()


def _save_eft_transaction(eft_record: EFTRecord, eft_file_model: EFTFileModel, is_error: bool):
    """Save or update EFT Transaction details record."""
    line_type = EFTFileLineType.TRANSACTION.value
    status_code = EFTProcessStatus.FAILED.value if is_error else EFTProcessStatus.IN_PROGRESS.value

    eft_transaction_model = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_number == eft_record.index)
        .filter(EFTTransactionModel.line_type == line_type)
        .one_or_none()
    )

    if eft_transaction_model is None:
        eft_transaction_model = EFTTransactionModel()

    if eft_record.transaction_description and eft_record.short_name_type:
        eft_short_name: EFTShortnameModel = _get_shortname(
            eft_record.transaction_description, eft_record.short_name_type, eft_record.generate_short_name, eft_record
        )
        eft_transaction_model.short_name_id = eft_short_name.id

    eft_transaction_model.line_type = line_type
    eft_transaction_model.line_number = eft_record.index
    eft_transaction_model.file_id = eft_file_model.id
    eft_transaction_model.status_code = status_code
    eft_transaction_model.error_messages = eft_record.get_error_messages()
    eft_transaction_model.batch_number = getattr(eft_record, "batch_number", None)
    eft_transaction_model.sequence_number = getattr(eft_record, "transaction_sequence", None)
    eft_transaction_model.jv_type = getattr(eft_record, "jv_type", None)
    eft_transaction_model.jv_number = getattr(eft_record, "jv_number", None)
    deposit_amount_cad = getattr(eft_record, "deposit_amount_cad", None)
    eft_transaction_model.deposit_date = getattr(eft_record, "deposit_datetime")
    eft_transaction_model.transaction_date = getattr(eft_record, "transaction_date")
    eft_transaction_model.deposit_amount_cents = deposit_amount_cad
    eft_transaction_model.save()

    eft_record.id = eft_transaction_model.id


def _update_transactions_to_fail(eft_file_model: EFTFileModel) -> int:
    """Set EFT transactions to fail status."""
    result = (
        db.session.query(EFTTransactionModel)
        .filter(
            EFTTransactionModel.file_id == eft_file_model.id,
            EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value,
        )
        .update(
            {EFTTransactionModel.status_code: EFTProcessStatus.FAILED.value},
            synchronize_session="fetch",
        )
    )

    eft_file_model.status_code = EFTProcessStatus.FAILED.value
    eft_file_model.save()

    return result


def _update_transactions_to_complete(eft_file_model: EFTFileModel) -> int:
    """Set EFT transactions to complete status if they are currently in progress."""
    result = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.status_code == EFTProcessStatus.IN_PROGRESS.value)
        .update(
            {EFTTransactionModel.status_code: EFTProcessStatus.COMPLETED.value},
            synchronize_session="fetch",
        )
    )
    db.session.commit()

    return result


def _get_shortname(
    short_name: str, short_name_type: str, generate_short_name: bool = False, eft_record: EFTRecord = None
) -> EFTShortnameModel:
    """Save short name if it doesn't exist."""
    eft_short_name = (
        (
            db.session.query(EFTShortnameModel)
            .filter(EFTShortnameModel.short_name == short_name)
            .filter(EFTShortnameModel.type == short_name_type)
            .one_or_none()
        )
        if not generate_short_name
        else None
    )

    if eft_short_name is None:
        eft_short_name = EFTShortnameModel()
        eft_short_name.type = short_name_type
        eft_short_name.short_name = short_name
        if generate_short_name:
            generated_short_name = f"{short_name} {EFTShortnameModel.get_next_short_name_seq()}"
            eft_short_name.short_name = generated_short_name
            eft_short_name.is_generated = True
            eft_record.transaction_description = generated_short_name
        eft_short_name.save()

    return eft_short_name


def _shortname_balance_as_dict(eft_transactions: List[EFTRecord]) -> Dict:
    """Create a dictionary mapping for shortname and total deposits from TDI17 file."""
    shortname_balance = {}

    for eft_transaction in eft_transactions:
        # Skip any transactions with errors
        if eft_transaction.has_errors():
            continue

        short_name = eft_transaction.transaction_description
        shortname_type = eft_transaction.short_name_type
        deposit_amount = eft_transaction.deposit_amount_cad / 100
        deposit_date = eft_transaction.deposit_datetime
        transaction = {"id": eft_transaction.id, "deposit_amount": deposit_amount, "deposit_date": deposit_date}

        shortname_balance.setdefault(short_name, {"balance": 0})
        shortname_balance[short_name]["short_name_type"] = shortname_type
        shortname_balance[short_name]["balance"] += deposit_amount
        shortname_balance[short_name].setdefault("transactions", []).append(transaction)

    return shortname_balance


def _filter_eft_transactions(eft_transactions: List[EFTRecord], eft_location_id: str) -> List[EFTRecord]:
    """Filter down EFT Transactions."""
    eft_transactions = [
        transaction
        for transaction in eft_transactions
        if (
            transaction.has_errors()
            or (
                transaction.short_name_type in [EFTShortnameType.EFT.value, EFTShortnameType.WIRE.value]
                and transaction.location_id == eft_location_id
            )
        )
    ]
    return eft_transactions
