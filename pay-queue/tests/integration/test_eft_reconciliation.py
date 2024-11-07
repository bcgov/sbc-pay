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

"""Tests to assure the EFT Reconciliation.

Test-Suite to ensure that the EFT Reconciliation queue service and parser is working as expected.
"""
from datetime import datetime
from typing import List

from pay_api import db
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTShortnamesHistorical as EFTHistoryModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services import EFTShortNamesService
from pay_api.utils.enums import (
    EFTCreditInvoiceStatus,
    EFTFileLineType,
    EFTHistoricalTypes,
    EFTProcessStatus,
    EFTShortnameStatus,
    EFTShortnameType,
    InvoiceStatus,
    PaymentMethod,
    StatementFrequency,
)
from sbc_common_components.utils.enums import QueueMessageTypes
from sqlalchemy import text

from pay_queue.services.eft import EFTRecord
from pay_queue.services.eft.eft_enums import EFTConstants
from tests.integration.factory import (
    factory_create_eft_account,
    factory_invoice,
    factory_statement,
    factory_statement_invoices,
    factory_statement_settings,
)
from tests.integration.utils import add_file_event_to_queue_and_process, create_and_upload_eft_file
from tests.utilities.factory_utils import factory_eft_header, factory_eft_record, factory_eft_trailer


def test_eft_tdi17_fail_header(session, app, client, mocker):
    """Test EFT Reconciliations properly fails for a bad EFT header."""
    mock_send_email = mocker.patch("pay_queue.services.eft.eft_reconciliation.send_error_email")
    # Generate file with invalid header
    file_name: str = "test_eft_tdi17.txt"
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="FAIL",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )

    create_and_upload_eft_file(file_name, [header])

    add_file_event_to_queue_and_process(client, file_name, QueueMessageTypes.EFT_FILE_UPLOADED.value)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.id is not None
    assert eft_file_model.file_ref == file_name
    assert eft_file_model.status_code == EFTProcessStatus.FAILED.value
    assert eft_file_model.created_on is not None
    assert eft_file_model.file_creation_date is None
    assert eft_file_model.deposit_from_date == datetime(2023, 8, 10)
    assert eft_file_model.deposit_to_date == datetime(2023, 8, 10)
    assert eft_file_model.number_of_details is None
    assert eft_file_model.total_deposit_cents is None

    eft_header_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is not None
    assert eft_header_transaction.id is not None
    assert eft_header_transaction.file_id == eft_file_model.id
    assert eft_header_transaction.line_type == EFTFileLineType.HEADER.value
    assert eft_header_transaction.status_code == EFTProcessStatus.FAILED.value
    assert eft_header_transaction.line_number == 0
    assert len(eft_header_transaction.error_messages) == 1
    assert eft_header_transaction.error_messages[0] == "Invalid header creation date time."

    eft_trailer_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is None

    eft_transactions: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert not bool(eft_transactions)

    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args[0]
    expected_error = "Failed to process file test_eft_tdi17.txt with an invalid header or trailer."
    actual_error = call_args[0].error_messages[0]["error"]
    assert expected_error == actual_error


def test_eft_tdi17_fail_trailer(session, app, client, mocker):
    """Test EFT Reconciliations properly fails for a bad EFT trailer."""
    mock_send_email = mocker.patch("pay_queue.services.eft.eft_reconciliation.send_error_email")
    # Generate file with invalid trailer
    file_name: str = "test_eft_tdi17.txt"
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )
    trailer = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="A",
        total_deposit_amount="3733750",
    )

    create_and_upload_eft_file(file_name, [header, trailer])

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.id is not None
    assert eft_file_model.file_ref == file_name
    assert eft_file_model.status_code == EFTProcessStatus.FAILED.value
    assert eft_file_model.created_on is not None
    assert eft_file_model.file_creation_date == datetime(2023, 8, 14, 16, 1)
    assert eft_file_model.deposit_from_date == datetime(2023, 8, 10)
    assert eft_file_model.deposit_to_date == datetime(2023, 8, 10)
    assert eft_file_model.number_of_details is None
    assert eft_file_model.total_deposit_cents == 3733750

    eft_trailer_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is not None
    assert eft_trailer_transaction.id is not None
    assert eft_trailer_transaction.file_id == eft_file_model.id
    assert eft_trailer_transaction.line_type == EFTFileLineType.TRAILER.value
    assert eft_trailer_transaction.status_code == EFTProcessStatus.FAILED.value
    assert eft_trailer_transaction.line_number == 1
    assert len(eft_trailer_transaction.error_messages) == 1
    assert eft_trailer_transaction.error_messages[0] == "Invalid trailer number of details value."

    eft_header_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is None

    eft_transactions: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert not bool(eft_transactions)

    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args[0]
    expected_error = "Failed to process file test_eft_tdi17.txt with an invalid header or trailer."
    actual_error = call_args[0].error_messages[0]["error"]
    assert expected_error == actual_error


def test_eft_tdi17_fail_transactions(session, app, client, mocker):
    """Test EFT Reconciliations properly fails for a bad EFT trailer."""
    mock_send_email = mocker.patch("pay_queue.services.eft.eft_reconciliation.send_error_email")
    # Generate file with invalid trailer
    file_name: str = "test_eft_tdi17.txt"
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )
    trailer = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="1",
        total_deposit_amount="3733750",
    )

    transaction_1 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="ABC123",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="FAIL",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    create_and_upload_eft_file(file_name, [header, transaction_1, trailer])

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.id is not None
    assert eft_file_model.file_ref == file_name
    assert eft_file_model.status_code == EFTProcessStatus.FAILED.value
    assert eft_file_model.created_on is not None
    assert eft_file_model.file_creation_date == datetime(2023, 8, 14, 16, 1)
    assert eft_file_model.deposit_from_date == datetime(2023, 8, 10)
    assert eft_file_model.deposit_to_date == datetime(2023, 8, 10)
    assert eft_file_model.number_of_details == 1
    assert eft_file_model.total_deposit_cents == 3733750

    eft_trailer_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is None

    eft_header_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is None

    eft_transactions: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert eft_transactions is not None
    assert len(eft_transactions) == 1
    assert eft_transactions[0].error_messages[0] == "Invalid transaction deposit amount CAD."

    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args[0]
    assert "Invalid transaction deposit amount CAD." == call_args[0].error_messages[0]["error"]


def test_eft_tdi17_basic_process(session, app, client):
    """Test EFT Reconciliations worker is able to create basic EFT processing records."""
    # Generate happy path file
    file_name: str = "test_eft_tdi17.txt"
    generate_basic_tdi17_file(file_name)

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.id is not None
    assert eft_file_model.file_ref == file_name
    assert eft_file_model.created_on is not None
    assert eft_file_model.file_creation_date == datetime(2023, 8, 14, 16, 1)
    assert eft_file_model.deposit_from_date == datetime(2023, 8, 10)
    assert eft_file_model.deposit_to_date == datetime(2023, 8, 10)
    assert eft_file_model.number_of_details == 5
    assert eft_file_model.total_deposit_cents == 3733750

    # Complete - short name is not mapped but credited
    assert eft_file_model.status_code == EFTProcessStatus.COMPLETED.value

    # Stored as part of the EFT File record - expecting none when no errors
    eft_header_transaction = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is None

    # Stored as part of the EFT File record - expecting none when no errors
    eft_trailer_transaction = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is None

    eft_transactions: List[EFTTransactionModel] = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert eft_transactions is not None
    assert len(eft_transactions) == 3
    assert eft_transactions[0].short_name_id is not None
    assert eft_transactions[1].short_name_id is not None
    assert eft_transactions[2].short_name_id is not None

    eft_shortnames = db.session.query(EFTShortnameModel).all()

    assert eft_shortnames is not None
    assert len(eft_shortnames) == 3

    short_name_link_1 = EFTShortnameLinksModel.find_by_short_name_id(eft_shortnames[0].id)
    short_name_link_2 = EFTShortnameLinksModel.find_by_short_name_id(eft_shortnames[1].id)
    short_name_link_3 = EFTShortnameLinksModel.find_by_short_name_id(eft_shortnames[2].id)

    assert not short_name_link_1
    assert eft_shortnames[0].short_name == "ABC123"
    assert not short_name_link_2
    assert eft_shortnames[1].short_name == "DEF456"
    assert not short_name_link_3
    assert eft_shortnames[2].short_name == "FEDERAL PAYMENT CANADA 1"

    eft_credits: List[EFTCreditModel] = db.session.query(EFTCreditModel).order_by(EFTCreditModel.id).all()
    assert eft_credits is not None
    assert len(eft_credits) == 3
    assert eft_credits[0].short_name_id == eft_shortnames[0].id
    assert eft_credits[0].eft_file_id == eft_file_model.id
    assert eft_credits[0].amount == 135
    assert eft_credits[0].remaining_amount == 135
    assert eft_credits[0].eft_transaction_id == eft_transactions[0].id
    assert eft_credits[1].short_name_id == eft_shortnames[1].id
    assert eft_credits[1].eft_file_id == eft_file_model.id
    assert eft_credits[1].amount == 5250
    assert eft_credits[1].remaining_amount == 5250
    assert eft_credits[1].eft_transaction_id == eft_transactions[1].id
    assert eft_credits[2].short_name_id == eft_shortnames[2].id
    assert eft_credits[2].eft_file_id == eft_file_model.id
    assert eft_credits[2].amount == 100
    assert eft_credits[2].remaining_amount == 100
    assert eft_credits[2].eft_transaction_id == eft_transactions[2].id


    # Expecting no credit links as they have not been applied to invoices
    eft_credit_invoice_links: List[EFTCreditInvoiceLinkModel] = db.session.query(EFTCreditInvoiceLinkModel).all()
    assert not eft_credit_invoice_links

    history: List[EFTHistoryModel] = db.session.query(EFTHistoryModel).order_by(EFTHistoryModel.id).all()
    assert_funds_received_history(eft_credits[0], history[0])
    assert_funds_received_history(eft_credits[1], history[1])


def assert_funds_received_history(
    eft_credit: EFTCreditModel,
    eft_history: EFTHistoryModel,
    assert_balance: bool = True,
):
    """Assert credit and history records match."""
    assert eft_history.short_name_id == eft_credit.short_name_id
    assert eft_history.amount == eft_credit.amount
    assert eft_history.transaction_type == EFTHistoricalTypes.FUNDS_RECEIVED.value
    assert eft_history.hidden is False
    assert eft_history.is_processing is False
    assert eft_history.statement_number is None
    if assert_balance:
        assert eft_history.credit_balance == eft_credit.amount


def test_eft_tdi17_process(session, app, client):
    """Test EFT Reconciliations worker."""
    payment_account, eft_shortname, invoice = create_test_data()

    assert payment_account is not None
    assert eft_shortname is not None
    assert invoice is not None
    # Generate happy path file
    file_name: str = "test_eft_tdi17.txt"
    generate_tdi17_file(file_name)

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.id is not None
    assert eft_file_model.file_ref == file_name
    assert eft_file_model.status_code == EFTProcessStatus.COMPLETED.value
    assert eft_file_model.created_on is not None
    assert eft_file_model.file_creation_date == datetime(2023, 8, 14, 16, 1)
    assert eft_file_model.deposit_from_date == datetime(2023, 8, 10)
    assert eft_file_model.deposit_to_date == datetime(2023, 8, 10)
    assert eft_file_model.number_of_details == 5
    assert eft_file_model.total_deposit_cents == 3733750

    # Stored as part of the EFT File record - expecting none when no errors
    eft_header_transaction = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is None

    # Stored as part of the EFT File record - expecting none when no errors
    eft_trailer_transaction = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is None

    eft_transactions = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert eft_transactions is not None
    assert len(eft_transactions) == 3
    assert eft_transactions[0].short_name_id is not None
    assert eft_transactions[1].short_name_id is not None
    assert eft_transactions[2].short_name_id is not None

    eft_shortnames = db.session.query(EFTShortnameModel).all()
    short_name_link_1: EFTShortnameLinksModel = EFTShortnameLinksModel.find_by_short_name_id(eft_shortnames[0].id)[0]
    short_name_link_2: EFTShortnameLinksModel = EFTShortnameLinksModel.find_by_short_name_id(eft_shortnames[1].id)

    assert eft_shortnames is not None
    assert len(eft_shortnames) == 2
    assert short_name_link_1
    assert short_name_link_1.auth_account_id == payment_account.auth_account_id
    assert eft_shortnames[0].short_name == "TESTSHORTNAME"
    assert not short_name_link_2
    assert eft_shortnames[1].short_name == "ABC123"

    eft_credits: List[EFTCreditModel] = db.session.query(EFTCreditModel).order_by(EFTCreditModel.id).all()
    history: List[EFTHistoryModel] = db.session.query(EFTHistoryModel).order_by(EFTHistoryModel.id).all()
    assert_funds_received_history(eft_credits[0], history[0])
    assert_funds_received_history(eft_credits[1], history[1], False)
    assert history[1].credit_balance == eft_credits[0].amount + eft_credits[1].amount
    assert_funds_received_history(eft_credits[2], history[2])


def test_eft_tdi17_rerun(session, app, client):
    """Test EFT Reconciliations can be re-executed with a corrected file."""
    payment_account, eft_shortname, invoice = create_test_data()

    # Generate file with invalid trailer
    file_name: str = "test_eft_tdi17.txt"
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )
    trailer = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="1",
        total_deposit_amount="3733750",
    )

    transaction_1 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="MISC PAYMENT TESTSHORTNAME",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="FAIL",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    create_and_upload_eft_file(file_name, [header, transaction_1, trailer])

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.status_code == EFTProcessStatus.FAILED.value

    eft_trailer_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is None

    eft_header_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is None

    eft_transactions: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert eft_transactions is not None
    assert len(eft_transactions) == 1
    assert eft_transactions[0].error_messages[0] == "Invalid transaction deposit amount CAD."

    # Correct transaction error and re-process
    transaction_1 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="MISC PAYMENT TESTSHORTNAME",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="13500",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    create_and_upload_eft_file(file_name, [header, transaction_1, trailer])
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Check file is completed after correction
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.status_code == EFTProcessStatus.COMPLETED.value

    eft_trailer_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value)
        .one_or_none()
    )

    assert eft_trailer_transaction is None

    eft_header_transaction: EFTTransactionModel = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value)
        .one_or_none()
    )

    assert eft_header_transaction is None

    eft_transactions: List[EFTTransactionModel] = (
        db.session.query(EFTTransactionModel)
        .filter(EFTTransactionModel.file_id == eft_file_model.id)
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        .all()
    )

    assert eft_transactions is not None
    assert len(eft_transactions) == 1
    assert len(eft_transactions[0].error_messages) == 0
    assert eft_transactions[0].status_code == EFTProcessStatus.COMPLETED.value
    assert eft_transactions[0].deposit_amount_cents == 13500


def test_eft_multiple_generated_short_names(session, app, client):
    """Test EFT Reconciliations worker is able to generate short names by sequence."""
    file_name: str = "test_eft_tdi17.txt"
    create_generated_short_names_file(file_name)
    session.execute(text("ALTER SEQUENCE eft_short_name_seq RESTART WITH 1"))
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = (
        db.session.query(EFTFileModel).filter(EFTFileModel.file_ref == file_name).one_or_none()
    )

    assert eft_file_model is not None
    assert eft_file_model.id is not None
    assert eft_file_model.file_ref == file_name
    assert eft_file_model.created_on is not None
    assert eft_file_model.file_creation_date == datetime(2023, 8, 14, 16, 1)
    assert eft_file_model.deposit_from_date == datetime(2023, 8, 10)
    assert eft_file_model.deposit_to_date == datetime(2023, 8, 10)
    assert eft_file_model.number_of_details == 2
    assert eft_file_model.total_deposit_cents == 20000

    # Complete - short name is not mapped but credited
    assert eft_file_model.status_code == EFTProcessStatus.COMPLETED.value
    eft_shortnames = db.session.query(EFTShortnameModel).all()

    assert eft_shortnames is not None
    assert len(eft_shortnames) == 2

    assert eft_shortnames[0].short_name == f'{EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN} 1'
    assert eft_shortnames[1].short_name == f'{EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN} 2'


def create_test_data():
    """Create test seed data."""
    payment_account = factory_create_eft_account()
    eft_short_name = EFTShortnameModel(short_name="TESTSHORTNAME", type=EFTShortnameType.EFT.value).save()
    EFTShortnameLinksModel(
        eft_short_name_id=eft_short_name.id,
        auth_account_id=payment_account.auth_account_id,
        status_code=EFTShortnameStatus.LINKED.value,
        updated_by="IDIR/JSMITH",
        updated_by_name="IDIR/JSMITH",
        updated_on=datetime.now(),
    ).save()

    invoice = factory_invoice(
        payment_account=payment_account,
        status_code=InvoiceStatus.APPROVED.value,
        total=150.50,
        service_fees=1.50,
        payment_method_code=PaymentMethod.EFT.value,
    )

    return payment_account, eft_short_name, invoice


def generate_basic_tdi17_file(file_name: str):
    """Generate a complete TDI17 EFT file."""
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )

    trailer = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="5",
        total_deposit_amount="3733750",
    )

    transaction_1 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description=f"{EFTRecord.EFT_DESCRIPTION_PATTERN} ABC123",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="13500",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_2 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="",
        location_id="85004",
        transaction_sequence="002",
        transaction_description=f"{EFTRecord.WIRE_DESCRIPTION_PATTERN} DEF456",
        deposit_amount="525000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="525000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_3 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="003",
        transaction_description=f"{EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN}",
        deposit_amount="10000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="10000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_4 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="003",
        transaction_description="SHOULDIGNORE",
        deposit_amount="525000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="525000",
        destination_bank_number="0004",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_5 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="005",
        transaction_description=f"{EFTRecord.PAD_DESCRIPTION_PATTERN} SHOULDIGNORE",
        deposit_amount="525000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="525000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    create_and_upload_eft_file(
        file_name,
        [header, transaction_1, transaction_2, transaction_3, transaction_4, transaction_5, trailer],
    )


def generate_tdi17_file(file_name: str):
    """Generate a complete TDI17 EFT file."""
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )

    trailer = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="5",
        total_deposit_amount="3733750",
    )

    transaction_1 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description=f"{EFTRecord.EFT_DESCRIPTION_PATTERN} TESTSHORTNAME",
        deposit_amount="10000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="10000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_2 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="",
        location_id="85004",
        transaction_sequence="002",
        transaction_description=f"{EFTRecord.EFT_DESCRIPTION_PATTERN} TESTSHORTNAME",
        deposit_amount="5050",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="5050",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_3 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="003",
        transaction_description=f"{EFTRecord.WIRE_DESCRIPTION_PATTERN} ABC123",
        deposit_amount="35150",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="35150",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_4 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="004",
        transaction_description=f"{EFTRecord.PAD_DESCRIPTION_PATTERN} SHOULDIGNORE",
        deposit_amount="525000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="525000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    create_and_upload_eft_file(
        file_name,
        [header, transaction_1, transaction_2, transaction_3, transaction_4, trailer],
    )


def create_generated_short_names_file(file_name: str):
    """Generate multiple TDI17 transactions that will generate short names to test sequencing."""
    header = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )

    trailer = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="2",
        total_deposit_amount="20000",
    )

    transaction_1 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description=f"{EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN}",
        deposit_amount="10000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="10000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    transaction_2 = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="002",
        transaction_description=f"{EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN}",
        deposit_amount="10000",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="10000",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    create_and_upload_eft_file(
        file_name,
        [header, transaction_1, transaction_2, trailer],
    )


def create_statement_from_invoices(account: PaymentAccountModel, invoices: List[InvoiceModel]):
    """Generate a statement from a list of invoices."""
    statement_settings = factory_statement_settings(
        pay_account_id=account.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement = factory_statement(
        payment_account_id=account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=statement_settings.id,
    )
    for invoice in invoices:
        factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)
    return statement


def test_apply_pending_payments(session, app, client):
    """Test automatically applying a pending eft credit invoice link when there is a credit."""
    payment_account, eft_short_name, invoice = create_test_data()
    create_statement_from_invoices(payment_account, [invoice])
    file_name: str = "test_eft_tdi17.txt"
    generate_tdi17_file(file_name)

    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )
    short_name_id = eft_short_name.id
    eft_credit_balance = EFTCreditModel.get_eft_credit_balance(short_name_id)
    assert eft_credit_balance == 0

    short_name_links = EFTShortNamesService.get_shortname_links(short_name_id)
    assert short_name_links["items"]
    assert len(short_name_links["items"]) == 1

    short_name_link = short_name_links["items"][0]
    assert short_name_link.get("has_pending_payment") is True
    assert short_name_link.get("amount_owing") == 150.50


def test_skip_on_existing_pending_payments(session, app, client):
    """Test auto payment skipping payment when there exists a pending payment."""
    payment_account, eft_short_name, invoice = create_test_data()
    file_name: str = "test_eft_tdi17.txt"
    generate_tdi17_file(file_name)
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    create_statement_from_invoices(payment_account, [invoice])
    eft_credits = EFTCreditModel.get_eft_credits(eft_short_name.id)

    # Add an unexpected PENDING record to test that processing skips for this account
    EFTCreditInvoiceLinkModel(
        eft_credit_id=eft_credits[0].id,
        status_code=EFTCreditInvoiceStatus.PENDING.value,
        invoice_id=invoice.id,
        amount=invoice.total,
        link_group_id=1,
    )

    short_name_id = eft_short_name.id
    eft_credit_balance = EFTCreditModel.get_eft_credit_balance(short_name_id)
    # Assert credit balance is not spent due to an expected already PENDING state
    assert eft_credit_balance == 150.50


def test_skip_on_insufficient_balance(session, app, client):
    """Test auto payment skipping payment when there is an insufficient eft credit balance."""
    payment_account, eft_short_name, invoice = create_test_data()
    invoice.total = 99999
    invoice.save()
    file_name: str = "test_eft_tdi17.txt"
    generate_tdi17_file(file_name)
    add_file_event_to_queue_and_process(
        client,
        file_name=file_name,
        message_type=QueueMessageTypes.EFT_FILE_UPLOADED.value,
    )

    create_statement_from_invoices(payment_account, [invoice])

    short_name_id = eft_short_name.id
    eft_credit_balance = EFTCreditModel.get_eft_credit_balance(short_name_id)
    assert eft_credit_balance == 150.50

    short_name_links = EFTShortNamesService.get_shortname_links(short_name_id)
    assert short_name_links["items"]
    assert len(short_name_links["items"]) == 1

    short_name_link = short_name_links["items"][0]
    assert short_name_link.get("has_pending_payment") is False
    assert short_name_link.get("amount_owing") == 99999
