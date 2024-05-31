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

"""Tests to assure the EFT transactions end-point.

Test-Suite to ensure that the /eft-shortnames/{id}/transactions endpoint is working as expected.
"""

from datetime import datetime

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.utils.enums import (
    EFTCreditInvoiceStatus, EFTFileLineType, EFTProcessStatus, InvoiceStatus, PaymentMethod, Role, StatementFrequency)
from tests.utilities.base_test import (
    factory_eft_file, factory_eft_shortname, factory_eft_shortname_link, factory_invoice, factory_payment_account,
    factory_statement, factory_statement_invoices, factory_statement_settings, get_claims, token_header)


def assert_funds_received(result_dict: dict, short_name: EFTShortnamesModel, transaction: EFTTransactionModel):
    """Assert funds received rows."""
    date_format = '%Y-%m-%dT%H:%M:%S'
    assert result_dict['transactionId'] == transaction.id
    assert not result_dict['accountId']
    assert not result_dict['accountName']
    assert not result_dict['accountBranch']
    assert not result_dict['statementId']
    assert result_dict['shortNameId'] == short_name.id
    assert result_dict['transactionAmount'] == transaction.deposit_amount_cents / 100
    assert datetime.strptime(result_dict['transactionDate'], date_format) == transaction.deposit_date
    assert result_dict['transactionDescription'] == 'Funds Received'


def test_search_short_name_funds_received(session, client, jwt, app):
    """Assert that EFT short names funds received can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # create test data
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                              auth_account_id='1234', name='ABC-BRANCH', branch_name='BRANCH').save()
    eft_file: EFTFileModel = factory_eft_file()
    short_name_1 = factory_eft_shortname(short_name='TESTSHORTNAME1').save()
    short_name_2 = factory_eft_shortname(short_name='TESTSHORTNAME2').save()
    factory_eft_shortname_link(
        short_name_id=short_name_2.id,
        auth_account_id='1234',
        updated_by='IDIR/JSMITH'
    ).save()

    # short_name_1 transactions
    s1_transaction1: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 4, 2, 30),
        deposit_date=datetime(2024, 1, 5, 10, 5),
        deposit_amount_cents=10150,
        short_name_id=short_name_1.id

    ).save()

    s1_transaction2 = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 3, 30),
        deposit_date=datetime(2024, 1, 6, 10, 5),
        deposit_amount_cents=10250,
        short_name_id=short_name_1.id

    ).save()

    s1_transaction3 = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 10, 2, 30),
        deposit_date=datetime(2024, 1, 11, 10, 5),
        deposit_amount_cents=30150,
        short_name_id=short_name_1.id
    ).save()

    # short_name_2 transactions
    s2_transaction1: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 15, 2, 30),
        deposit_date=datetime(2024, 1, 16, 10, 5),
        deposit_amount_cents=30250,
        short_name_id=short_name_2.id

    ).save()

    # short name 2 credit
    EFTCreditModel(
        eft_file_id=eft_file.id,
        eft_transaction_id=s2_transaction1.id,
        short_name_id=short_name_2.id,
        payment_account_id=payment_account.id,
        amount=302.50,
        remaining_amount=302.50
    ).save()

    EFTCreditModel(
        eft_file_id=eft_file.id,
        eft_transaction_id=s2_transaction1.id,
        short_name_id=short_name_2.id,
        payment_account_id=payment_account.id,
        amount=10.25,
        remaining_amount=10.25
    ).save()

    # Assert search returns unlinked short names
    rv = client.get(f'/api/v1/eft-shortnames/{short_name_1.id}/transactions', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['total'] == 3
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 3
    # Most recent transaction date first
    assert_funds_received(result_dict['items'][0], short_name_1, s1_transaction3)
    assert_funds_received(result_dict['items'][1], short_name_1, s1_transaction2)
    assert_funds_received(result_dict['items'][2], short_name_1, s1_transaction1)

    # Assert search returns funds received rows
    rv = client.get(f'/api/v1/eft-shortnames/{short_name_2.id}/transactions', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_funds_received(result_dict['items'][0], short_name_2, s2_transaction1)


def test_search_short_name_funds_applied(session, client, jwt, app):
    """Assert that EFT short names funds applied can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # create test data
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                              auth_account_id='1234', name='ABC-BRANCH', branch_name='BRANCH').save()
    eft_file: EFTFileModel = factory_eft_file()
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME1').save()

    # Set up scenario where statement invoices have been paid via EFT
    # EFT Transactions from TDI17 have been processed and EFT Credit records have been created and used.
    transaction1: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 4, 2, 30),
        deposit_date=datetime(2024, 1, 5, 10, 5),
        deposit_amount_cents=10150,
        short_name_id=short_name.id).save()
    t1_eft_credit = EFTCreditModel(
        eft_file_id=eft_file.id,
        eft_transaction_id=transaction1.id,
        short_name_id=short_name.id,
        payment_account_id=payment_account.id,
        amount=101.50,
        remaining_amount=0).save()

    transaction2 = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 3, 30),
        deposit_date=datetime(2024, 1, 6, 10, 5),
        deposit_amount_cents=10000,
        short_name_id=short_name.id).save()

    t2_eft_credit = EFTCreditModel(
        eft_file_id=eft_file.id,
        eft_transaction_id=transaction2.id,
        short_name_id=short_name.id,
        payment_account_id=payment_account.id,
        amount=10.25,
        remaining_amount=10.25).save()

    # Create statement and invoices that have been paid
    statement_payment_date = datetime(2024, 1, 10, 9, 0)
    invoice_1 = factory_invoice(payment_account, payment_method_code=PaymentMethod.EFT.value,
                                total=105.50, paid=0, status_code=InvoiceStatus.PAID.value).save()
    invoice_1.payment_date = statement_payment_date
    invoice_1.save()
    invoice_2 = factory_invoice(payment_account, payment_method_code=PaymentMethod.EFT.value,
                                total=96.00, paid=0, status_code=InvoiceStatus.PAID.value).save()
    invoice_2.payment_date = statement_payment_date
    invoice_2.save()

    statement_settings = factory_statement_settings(payment_account_id=payment_account.id,
                                                    frequency=StatementFrequency.MONTHLY.value)
    statement = factory_statement(payment_account_id=payment_account.id,
                                  frequency=StatementFrequency.MONTHLY.value,
                                  statement_settings_id=statement_settings.id)
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice_1.id)
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice_2.id)

    # Establish EFT Credit to invoice links for applied funds and amount
    EFTCreditInvoiceLinkModel(
        eft_credit_id=t1_eft_credit.id,
        invoice_id=invoice_1.id,
        amount=101.50,
        status_code=EFTCreditInvoiceStatus.COMPLETED.value
    ).save()

    # Testing transactions query where first set of credits were insufficient and a second set was applied
    # This should just roll up as a total amount paid
    EFTCreditInvoiceLinkModel(
        eft_credit_id=t2_eft_credit.id,
        invoice_id=invoice_1.id,
        amount=4.00,
        status_code=EFTCreditInvoiceStatus.COMPLETED.value
    ).save()

    # Remaining credit paid to invoice 2
    EFTCreditInvoiceLinkModel(
        eft_credit_id=t2_eft_credit.id,
        invoice_id=invoice_2.id,
        amount=96.00,
        status_code=EFTCreditInvoiceStatus.COMPLETED.value
    ).save()

    # Assert search returns funds received and funds applied rows
    rv = client.get(f'/api/v1/eft-shortnames/{short_name.id}/transactions', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['total'] == 3
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 3

    statement_paid = result_dict['items'][0]
    date_format = '%Y-%m-%dT%H:%M:%S'
    assert not statement_paid['transactionId']
    assert statement_paid['statementId'] == statement.id
    assert statement_paid['accountId'] == payment_account.auth_account_id
    assert statement_paid['accountName'] == 'ABC'
    assert statement_paid['accountBranch'] == 'BRANCH'
    assert statement_paid['shortNameId'] == short_name.id
    assert statement_paid['transactionAmount'] == 201.50
    assert datetime.strptime(statement_paid['transactionDate'], date_format) == statement_payment_date
    assert statement_paid['transactionDescription'] == 'Statement Paid'

    assert_funds_received(result_dict['items'][1], short_name, transaction2)
    assert_funds_received(result_dict['items'][2], short_name, transaction1)
