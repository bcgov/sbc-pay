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

import pytest
from entity_queue_common.service_utils import subscribe_to_queue
from flask import current_app
from pay_api import db
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import (
    EFTFileLineType, EFTProcessStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus)

from reconciliations.eft.eft_enums import EFTConstants
from tests.integration.factory import factory_create_eft_account, factory_invoice
from tests.integration.utils import create_and_upload_eft_file, helper_add_eft_event_to_queue
from tests.utilities.factory_utils import factory_eft_header, factory_eft_record, factory_eft_trailer


@pytest.mark.asyncio
async def test_eft_tdi17_fail_header(session, app, stan_server, event_loop, client_id, events_stan, future,
                                     mock_publish):
    """Test EFT Reconciliations properly fails for a bad EFT header."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # Generate file with invalid header
    file_name: str = 'test_eft_tdi17.txt'
    header = factory_eft_header(record_type=EFTConstants.HEADER_RECORD_TYPE.value, file_creation_date='20230814',
                                file_creation_time='FAIL', deposit_start_date='20230810', deposit_end_date='20230810')

    create_and_upload_eft_file(file_name, [header])

    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

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

    eft_header_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is not None
    assert eft_header_transaction.id is not None
    assert eft_header_transaction.file_id == eft_file_model.id
    assert eft_header_transaction.line_type == EFTFileLineType.HEADER.value
    assert eft_header_transaction.status_code == EFTProcessStatus.FAILED.value
    assert eft_header_transaction.line_number == 0
    assert len(eft_header_transaction.error_messages) == 1
    assert eft_header_transaction.error_messages[0] == 'Invalid header creation date time.'

    eft_trailer_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is None

    eft_transactions: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert not bool(eft_transactions)


@pytest.mark.asyncio
async def test_eft_tdi17_fail_trailer(session, app, stan_server, event_loop, client_id, events_stan, future,
                                      mock_publish):
    """Test EFT Reconciliations properly fails for a bad EFT trailer."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # Generate file with invalid trailer
    file_name: str = 'test_eft_tdi17.txt'
    header = factory_eft_header(record_type=EFTConstants.HEADER_RECORD_TYPE.value, file_creation_date='20230814',
                                file_creation_time='1601', deposit_start_date='20230810', deposit_end_date='20230810')
    trailer = factory_eft_trailer(record_type=EFTConstants.TRAILER_RECORD_TYPE.value, number_of_details='A',
                                  total_deposit_amount='3733750')

    create_and_upload_eft_file(file_name, [header, trailer])

    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

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

    eft_trailer_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is not None
    assert eft_trailer_transaction.id is not None
    assert eft_trailer_transaction.file_id == eft_file_model.id
    assert eft_trailer_transaction.line_type == EFTFileLineType.TRAILER.value
    assert eft_trailer_transaction.status_code == EFTProcessStatus.FAILED.value
    assert eft_trailer_transaction.line_number == 1
    assert len(eft_trailer_transaction.error_messages) == 1
    assert eft_trailer_transaction.error_messages[0] == 'Invalid trailer number of details value.'

    eft_header_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is None

    eft_transactions: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert not bool(eft_transactions)


@pytest.mark.asyncio
async def test_eft_tdi17_fail_transactions(session, app, stan_server, event_loop, client_id, events_stan, future,
                                           mock_publish):
    """Test EFT Reconciliations properly fails for a bad EFT trailer."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # Generate file with invalid trailer
    file_name: str = 'test_eft_tdi17.txt'
    header = factory_eft_header(record_type=EFTConstants.HEADER_RECORD_TYPE.value, file_creation_date='20230814',
                                file_creation_time='1601', deposit_start_date='20230810', deposit_end_date='20230810')
    trailer = factory_eft_trailer(record_type=EFTConstants.TRAILER_RECORD_TYPE.value, number_of_details='1',
                                  total_deposit_amount='3733750')

    transaction_1 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='001',
                                       transaction_description='ABC123', deposit_amount='13500',
                                       currency='', exchange_adj_amount='0', deposit_amount_cad='FAIL',
                                       destination_bank_number='0003', batch_number='002400986', jv_type='I',
                                       jv_number='002425669', transaction_date='')

    create_and_upload_eft_file(file_name, [header, transaction_1, trailer])

    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

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

    eft_trailer_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is None

    eft_header_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is None

    eft_transactions: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert eft_transactions is not None
    assert len(eft_transactions) == 1
    assert eft_transactions[0].error_messages[0] == 'Invalid transaction deposit amount CAD.'


@pytest.mark.asyncio
async def test_eft_tdi17_basic_process(session, app, stan_server, event_loop, client_id, events_stan, future,
                                       mock_publish):
    """Test EFT Reconciliations worker is able to create basic EFT processing records."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # Generate happy path file
    file_name: str = 'test_eft_tdi17.txt'
    generate_basic_tdi17_file(file_name)

    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

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
    eft_header_transaction = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is None

    # Stored as part of the EFT File record - expecting none when no errors
    eft_trailer_transaction = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is None

    eft_transactions: List[EFTTransactionModel] = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert eft_transactions is not None
    assert len(eft_transactions) == 2
    assert eft_transactions[0].short_name_id is not None
    assert eft_transactions[1].short_name_id is not None

    eft_shortnames = db.session.query(EFTShortnameModel).all()

    assert eft_shortnames is not None
    assert len(eft_shortnames) == 2
    assert eft_shortnames[0].auth_account_id is None
    assert eft_shortnames[0].short_name == 'ABC123'
    assert eft_shortnames[1].auth_account_id is None
    assert eft_shortnames[1].short_name == 'DEF456'

    eft_credits: List[EFTCreditModel] = db.session.query(EFTCreditModel).all()
    assert eft_credits is not None
    assert len(eft_credits) == 2
    assert eft_credits[0].payment_account_id is None
    assert eft_credits[0].short_name_id == eft_shortnames[0].id
    assert eft_credits[0].eft_file_id == eft_file_model.id
    assert eft_credits[0].amount == 135
    assert eft_credits[0].remaining_amount == 135
    assert eft_credits[1].payment_account_id is None
    assert eft_credits[1].short_name_id == eft_shortnames[1].id
    assert eft_credits[1].eft_file_id == eft_file_model.id
    assert eft_credits[1].amount == 5250
    assert eft_credits[1].remaining_amount == 5250


@pytest.mark.asyncio
async def test_eft_tdi17_process(session, app, stan_server, event_loop, client_id, events_stan, future,
                                 mock_publish):
    """Test EFT Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    payment_account, eft_shortname, invoice = create_test_data()

    assert payment_account is not None
    assert eft_shortname is not None
    assert invoice is not None

    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # Generate happy path file
    file_name: str = 'test_eft_tdi17.txt'
    generate_tdi17_file(file_name)

    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

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
    eft_header_transaction = db.session.query(EFTTransactionModel)\
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is None

    # Stored as part of the EFT File record - expecting none when no errors
    eft_trailer_transaction = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is None

    eft_transactions = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert eft_transactions is not None
    assert len(eft_transactions) == 3
    assert eft_transactions[0].short_name_id is not None
    assert eft_transactions[1].short_name_id is not None
    assert eft_transactions[2].short_name_id is not None

    eft_shortnames = db.session.query(EFTShortnameModel).all()

    assert eft_shortnames is not None
    assert len(eft_shortnames) == 2
    assert eft_shortnames[0].auth_account_id == eft_shortname.auth_account_id
    assert eft_shortnames[0].short_name == 'TESTSHORTNAME'
    assert eft_shortnames[1].auth_account_id is None
    assert eft_shortnames[1].short_name == 'ABC123'

    today = datetime.now().date()

    # Assert Invoice is paid
    invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    expected_amount = 100
    assert invoice is not None
    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value
    assert invoice.payment_date is not None
    assert invoice.payment_date.date() == today
    assert invoice.paid == expected_amount
    assert invoice.total == expected_amount

    receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice.id, invoice.id)
    assert receipt is not None
    assert receipt.receipt_number == str(invoice.id)
    assert receipt.receipt_amount == expected_amount

    expected_invoice_number = f'{current_app.config["EFT_INVOICE_PREFIX"]}{invoice.id}'
    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)
    assert payment is not None
    assert payment.payment_date.date() == today
    assert payment.invoice_number == expected_invoice_number
    assert payment.payment_account_id == payment_account.id
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.payment_method_code == PaymentMethod.EFT.value
    assert payment.invoice_amount == expected_amount
    assert payment.paid_amount == expected_amount

    invoice_reference: InvoiceReferenceModel = InvoiceReferenceModel\
        .find_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.COMPLETED.value)

    assert invoice_reference is not None
    assert invoice_reference.invoice_id == invoice.id
    assert invoice_reference.invoice_number == payment.invoice_number
    assert invoice_reference.invoice_number == expected_invoice_number
    assert invoice_reference.status_code == InvoiceReferenceStatus.COMPLETED.value

    eft_credits: List[EFTCreditModel] = db.session.query(EFTCreditModel).all()
    assert eft_credits is not None
    assert len(eft_credits) == 2
    assert eft_credits[0].payment_account_id == payment_account.id
    assert eft_credits[0].short_name_id == eft_shortnames[0].id
    assert eft_credits[0].eft_file_id == eft_file_model.id
    assert eft_credits[0].amount == 50.5
    assert eft_credits[0].remaining_amount == 50.5
    assert eft_credits[1].payment_account_id is None
    assert eft_credits[1].short_name_id == eft_shortnames[1].id
    assert eft_credits[1].eft_file_id == eft_file_model.id
    assert eft_credits[1].amount == 351.5
    assert eft_credits[1].remaining_amount == 351.5


@pytest.mark.asyncio
async def test_eft_tdi17_rerun(session, app, stan_server, event_loop, client_id, events_stan, future,
                               mock_publish):
    """Test EFT Reconciliations can be re-executed with a corrected file."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    payment_account, eft_shortname, invoice = create_test_data()

    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # Generate file with invalid trailer
    file_name: str = 'test_eft_tdi17.txt'
    header = factory_eft_header(record_type=EFTConstants.HEADER_RECORD_TYPE.value, file_creation_date='20230814',
                                file_creation_time='1601', deposit_start_date='20230810', deposit_end_date='20230810')
    trailer = factory_eft_trailer(record_type=EFTConstants.TRAILER_RECORD_TYPE.value, number_of_details='1',
                                  total_deposit_amount='3733750')

    transaction_1 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='001',
                                       transaction_description='TESTSHORTNAME', deposit_amount='13500',
                                       currency='', exchange_adj_amount='0', deposit_amount_cad='FAIL',
                                       destination_bank_number='0003', batch_number='002400986', jv_type='I',
                                       jv_number='002425669', transaction_date='')

    create_and_upload_eft_file(file_name, [header, transaction_1, trailer])

    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Assert EFT File record was created
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

    assert eft_file_model is not None
    assert eft_file_model.status_code == EFTProcessStatus.FAILED.value

    eft_trailer_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is None

    eft_header_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is None

    eft_transactions: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert eft_transactions is not None
    assert len(eft_transactions) == 1
    assert eft_transactions[0].error_messages[0] == 'Invalid transaction deposit amount CAD.'

    # Correct transaction error and re-process
    transaction_1 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='001',
                                       transaction_description='TESTSHORTNAME', deposit_amount='13500',
                                       currency='', exchange_adj_amount='0', deposit_amount_cad='13500',
                                       destination_bank_number='0003', batch_number='002400986', jv_type='I',
                                       jv_number='002425669', transaction_date='')

    create_and_upload_eft_file(file_name, [header, transaction_1, trailer])
    await helper_add_eft_event_to_queue(events_stan, file_name=file_name)

    # Check file is completed after correction
    eft_file_model: EFTFileModel = db.session.query(EFTFileModel).filter(
        EFTFileModel.file_ref == file_name).one_or_none()

    assert eft_file_model is not None
    assert eft_file_model.status_code == EFTProcessStatus.COMPLETED.value

    eft_trailer_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRAILER.value).one_or_none()

    assert eft_trailer_transaction is None

    eft_header_transaction: EFTTransactionModel = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.HEADER.value).one_or_none()

    assert eft_header_transaction is None

    eft_transactions: List[EFTTransactionModel] = db.session.query(EFTTransactionModel) \
        .filter(EFTTransactionModel.file_id == eft_file_model.id) \
        .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    assert eft_transactions is not None
    assert len(eft_transactions) == 1
    assert len(eft_transactions[0].error_messages) == 0
    assert eft_transactions[0].status_code == EFTProcessStatus.COMPLETED.value
    assert eft_transactions[0].deposit_amount_cents == 13500

    today = datetime.now().date()
    # Assert Invoice is paid
    invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    expected_amount = 100
    assert invoice is not None
    assert invoice.payment_method_code == PaymentMethod.EFT.value
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value
    assert invoice.payment_date is not None
    assert invoice.payment_date.date() == today
    assert invoice.paid == expected_amount
    assert invoice.total == expected_amount

    receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice.id, invoice.id)
    assert receipt is not None
    assert receipt.receipt_number == str(invoice.id)
    assert receipt.receipt_amount == expected_amount

    expected_invoice_number = f'{current_app.config["EFT_INVOICE_PREFIX"]}{invoice.id}'
    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)
    assert payment is not None
    assert payment.payment_date.date() == today
    assert payment.invoice_number == expected_invoice_number
    assert payment.payment_account_id == payment_account.id
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.payment_method_code == PaymentMethod.EFT.value
    assert payment.invoice_amount == expected_amount

    invoice_reference: InvoiceReferenceModel = InvoiceReferenceModel \
        .find_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.COMPLETED.value)

    assert invoice_reference is not None
    assert invoice_reference.invoice_id == invoice.id
    assert invoice_reference.invoice_number == payment.invoice_number
    assert invoice_reference.invoice_number == expected_invoice_number
    assert invoice_reference.status_code == InvoiceReferenceStatus.COMPLETED.value

    eft_credits: List[EFTCreditModel] = db.session.query(EFTCreditModel).all()
    assert eft_credits is not None
    assert len(eft_credits) == 1
    assert eft_credits[0].payment_account_id == payment_account.id
    assert eft_credits[0].short_name_id == eft_shortname.id
    assert eft_credits[0].eft_file_id == eft_file_model.id
    assert eft_credits[0].amount == 35
    assert eft_credits[0].remaining_amount == 35


def create_test_data():
    """Create test seed data."""
    payment_account: PaymentAccountModel = factory_create_eft_account()
    eft_shortname: EFTShortnameModel = EFTShortnameModel(short_name='TESTSHORTNAME',
                                                         auth_account_id=payment_account.auth_account_id).save()

    invoice: InvoiceModel = factory_invoice(payment_account=payment_account, total=100, service_fees=10.0,
                                            payment_method_code=PaymentMethod.EFT.value)

    return payment_account, eft_shortname, invoice


def generate_basic_tdi17_file(file_name: str):
    """Generate a complete TDI17 EFT file."""
    header = factory_eft_header(record_type=EFTConstants.HEADER_RECORD_TYPE.value, file_creation_date='20230814',
                                file_creation_time='1601', deposit_start_date='20230810', deposit_end_date='20230810')

    trailer = factory_eft_trailer(record_type=EFTConstants.TRAILER_RECORD_TYPE.value, number_of_details='5',
                                  total_deposit_amount='3733750')

    transaction_1 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='001',
                                       transaction_description='ABC123', deposit_amount='13500',
                                       currency='', exchange_adj_amount='0', deposit_amount_cad='13500',
                                       destination_bank_number='0003', batch_number='002400986', jv_type='I',
                                       jv_number='002425669', transaction_date='')

    transaction_2 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='002',
                                       transaction_description='DEF456',
                                       deposit_amount='525000', currency='', exchange_adj_amount='0',
                                       deposit_amount_cad='525000', destination_bank_number='0003',
                                       batch_number='002400986', jv_type='I', jv_number='002425669',
                                       transaction_date='')

    create_and_upload_eft_file(file_name, [header, transaction_1, transaction_2, trailer])


def generate_tdi17_file(file_name: str):
    """Generate a complete TDI17 EFT file."""
    header = factory_eft_header(record_type=EFTConstants.HEADER_RECORD_TYPE.value, file_creation_date='20230814',
                                file_creation_time='1601', deposit_start_date='20230810', deposit_end_date='20230810')

    trailer = factory_eft_trailer(record_type=EFTConstants.TRAILER_RECORD_TYPE.value, number_of_details='5',
                                  total_deposit_amount='3733750')

    transaction_1 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='001',
                                       transaction_description='TESTSHORTNAME', deposit_amount='10000',
                                       currency='', exchange_adj_amount='0', deposit_amount_cad='10000',
                                       destination_bank_number='0003', batch_number='002400986', jv_type='I',
                                       jv_number='002425669', transaction_date='')

    transaction_2 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='002',
                                       transaction_description='TESTSHORTNAME',
                                       deposit_amount='5050', currency='', exchange_adj_amount='0',
                                       deposit_amount_cad='5050', destination_bank_number='0003',
                                       batch_number='002400986', jv_type='I', jv_number='002425669',
                                       transaction_date='')

    transaction_3 = factory_eft_record(record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value, ministry_code='AT',
                                       program_code='0146', deposit_date='20230810', deposit_time='0000',
                                       location_id='85004', transaction_sequence='003',
                                       transaction_description='ABC123', deposit_amount='35150',
                                       currency='', exchange_adj_amount='0', deposit_amount_cad='35150',
                                       destination_bank_number='0003', batch_number='002400986', jv_type='I',
                                       jv_number='002425669', transaction_date='')

    create_and_upload_eft_file(file_name, [header, transaction_1, transaction_2, transaction_3, trailer])
