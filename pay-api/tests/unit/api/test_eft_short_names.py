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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""

import json
from datetime import datetime

from flask import current_app

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import (
    EFTFileLineType, EFTProcessStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, Role)
from tests.utilities.base_test import (
    factory_eft_file, factory_eft_shortname, factory_invoice, factory_payment_account, get_claims, token_header)


def test_patch_eft_short_name(session, client, jwt, app):
    """Assert that an EFT short name account id can be patched."""
    token = jwt.create_jwt(get_claims(roles=[Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                            auth_account_id='1234').save()

    short_name = factory_eft_shortname(short_name='TESTSHORTNAME').save()
    rv = client.patch(f'/api/v1/eft-shortnames/{short_name.id}',
                      data=json.dumps({'accountId': '1234'}),
                      headers=headers)
    shortname_dict = rv.json
    assert rv.status_code == 200
    assert shortname_dict is not None
    assert shortname_dict['id'] is not None
    assert shortname_dict['shortName'] == 'TESTSHORTNAME'
    assert shortname_dict['accountId'] == '1234'


def test_patch_eft_short_name_validation(session, client, jwt, app):
    """Assert that invalid request is returned for existing short name."""
    token = jwt.create_jwt(get_claims(roles=[Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME', auth_account_id='1234').save()

    # Assert requires an auth account id for mapping
    rv = client.patch(f'/api/v1/eft-shortnames/{short_name.id}',
                      data=json.dumps({}),
                      headers=headers)

    shortname_dict = rv.json
    assert rv.status_code == 400
    assert shortname_dict['type'] == 'EFT_SHORT_NAME_ACCOUNT_ID_REQUIRED'

    # Assert cannot update short name with an existing mapped account id
    rv = client.patch(f'/api/v1/eft-shortnames/{short_name.id}',
                      data=json.dumps({'accountId': '2222'}),
                      headers=headers)

    shortname_dict = rv.json
    assert rv.status_code == 400
    assert shortname_dict['type'] == 'EFT_SHORT_NAME_ALREADY_MAPPED'


def assert_short_name(result_dict: dict, short_name: EFTShortnamesModel, transaction: EFTTransactionModel):
    """Assert short name result."""
    date_format = '%Y-%m-%dT%H:%M:%S'
    assert result_dict['shortName'] == short_name.short_name
    assert result_dict['accountId'] == short_name.auth_account_id
    assert result_dict['depositAmount'] == transaction.deposit_amount_cents / 100
    assert datetime.strptime(result_dict['depositDate'], date_format) == transaction.deposit_date
    assert result_dict['transactionId'] == transaction.id
    assert datetime.strptime(result_dict['transactionDate'], date_format) == transaction.transaction_date


def test_search_eft_short_names(session, client, jwt, app):
    """Assert that EFT short names can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Assert initial search returns empty items
    rv = client.get('/api/v1/eft-shortnames', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 0

    # create test data
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                              auth_account_id='1234',
                                              name='ABC-123',
                                              branch_name='123').save()

    eft_file: EFTFileModel = factory_eft_file()
    short_name_1 = factory_eft_shortname(short_name='TESTSHORTNAME1').save()
    short_name_2 = factory_eft_shortname(short_name='TESTSHORTNAME2', auth_account_id='1234').save()

    # short_name_1 transactions to test getting first payment
    s1_transaction1: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 2, 30),
        deposit_date=datetime(2024, 1, 6, 10, 5),
        deposit_amount_cents=10150,
        short_name_id=short_name_1.id

    ).save()

    # Identical to transaction 1 should not return duplicate short name rows - partitioned by transaction date, id
    EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 2, 30),
        deposit_date=datetime(2024, 1, 6, 10, 5),
        deposit_amount_cents=10250,
        short_name_id=short_name_1.id

    ).save()

    EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 10, 2, 30),
        deposit_date=datetime(2024, 1, 11, 10, 5),
        deposit_amount_cents=30150,
        short_name_id=short_name_1.id
    ).save()

    # short_name_2 transactions - to test date filters
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

    # Assert search returns unlinked short names
    rv = client.get('/api/v1/eft-shortnames?state=UNLINKED', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['shortName'] == 'TESTSHORTNAME1'
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)

    # Assert search returns linked short names with payment account name that has a branch
    rv = client.get('/api/v1/eft-shortnames?state=LINKED', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['shortName'] == 'TESTSHORTNAME2'
    assert result_dict['items'][0]['accountName'] == 'ABC'
    assert result_dict['items'][0]['accountBranch'] == '123'
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search account name
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountName=BC', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['accountName'] == 'ABC'
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search account branch
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountBranch=2', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['accountName'] == 'ABC'
    assert result_dict['items'][0]['accountBranch'] == '123'
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Update payment account to not have a branch name
    payment_account.name = 'ABC'
    payment_account.branch_name = None
    payment_account.save()

    # Assert search returns linked short names with payment account name that has no branch
    rv = client.get('/api/v1/eft-shortnames?state=LINKED', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['shortName'] == 'TESTSHORTNAME2'
    assert result_dict['items'][0]['accountName'] == 'ABC'
    assert result_dict['items'][0]['accountBranch'] is None
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search account name
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountName=BC', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['accountName'] == 'ABC'
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search query by no state will return all records
    rv = client.get('/api/v1/eft-shortnames', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 2
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)
    assert_short_name(result_dict['items'][1], short_name_2, s2_transaction1)

    # Assert search pagination - page 1 works
    rv = client.get('/api/v1/eft-shortnames?page=1&limit=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 1
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)

    # Assert search pagination - page 2 works
    rv = client.get('/api/v1/eft-shortnames?page=2&limit=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 2
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 1
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search text brings back both short names
    rv = client.get('/api/v1/eft-shortnames?shortName=SHORT', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 2
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)
    assert_short_name(result_dict['items'][1], short_name_2, s2_transaction1)

    # Assert search text brings back one short name
    rv = client.get('/api/v1/eft-shortnames?shortName=name1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)

    # Assert search transaction date
    rv = client.get('/api/v1/eft-shortnames?transactionDate=2024-01-05', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)

    # Assert search transaction date
    rv = client.get('/api/v1/eft-shortnames?depositDate=2024-01-16', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search deposit amount
    rv = client.get('/api/v1/eft-shortnames?depositAmount=101.50', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_1, s1_transaction1)

    # Assert search account id
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountId=1234', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)

    # Assert search account id list
    rv = client.get('/api/v1/eft-shortnames?accountIdList=1,1234', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['items'][0]['shortName'] == 'TESTSHORTNAME2'
    assert result_dict['items'][0]['accountName'] == 'ABC'
    assert result_dict['items'][0]['accountBranch'] is None
    assert_short_name(result_dict['items'][0], short_name_2, s2_transaction1)


def test_apply_eft_short_name_credits(session, client, jwt, app):
    """Assert that credits are applied to invoices when short name is mapped to an account."""
    token = jwt.create_jwt(get_claims(roles=[Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME').save()

    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                              auth_account_id='1234').save()
    invoice_1 = factory_invoice(payment_account, payment_method_code=PaymentMethod.EFT.value,
                                total=50, paid=0).save()
    invoice_2 = factory_invoice(payment_account, payment_method_code=PaymentMethod.EFT.value,
                                total=200, paid=0).save()
    eft_file = factory_eft_file('test.txt')

    eft_credit_1 = EFTCreditModel()
    eft_credit_1.eft_file_id = eft_file.id
    eft_credit_1.payment_account_id = payment_account.id
    eft_credit_1.amount = 50
    eft_credit_1.remaining_amount = 50
    eft_credit_1.short_name_id = short_name.id
    eft_credit_1.save()

    eft_credit_2 = EFTCreditModel()
    eft_credit_2.eft_file_id = eft_file.id
    eft_credit_2.payment_account_id = payment_account.id
    eft_credit_2.amount = 150
    eft_credit_2.remaining_amount = 150
    eft_credit_2.short_name_id = short_name.id
    eft_credit_2.save()

    rv = client.patch(f'/api/v1/eft-shortnames/{short_name.id}',
                      data=json.dumps({'accountId': '1234'}),
                      headers=headers)
    shortname_dict = rv.json
    assert rv.status_code == 200
    assert shortname_dict is not None
    assert shortname_dict['id'] is not None
    assert shortname_dict['shortName'] == 'TESTSHORTNAME'
    assert shortname_dict['accountId'] == '1234'

    # Assert credits have the correct remaining values
    assert eft_credit_1.remaining_amount == 0
    assert eft_credit_1.payment_account_id == payment_account.id
    assert eft_credit_2.remaining_amount == 0
    assert eft_credit_2.payment_account_id == payment_account.id

    today = datetime.now().date()

    # Assert details of fully paid invoice
    invoice_1_paid = 50
    assert invoice_1.payment_method_code == PaymentMethod.EFT.value
    assert invoice_1.invoice_status_code == InvoiceStatus.PAID.value
    assert invoice_1.payment_date is not None
    assert invoice_1.payment_date.date() == today
    assert invoice_1.paid == invoice_1_paid
    assert invoice_1.total == invoice_1_paid

    receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_1.id, invoice_1.id)
    assert receipt is not None
    assert receipt.receipt_number == str(invoice_1.id)
    assert receipt.receipt_amount == invoice_1_paid

    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice_1.id)
    assert payment is not None
    assert payment.payment_date.date() == today
    assert payment.invoice_number == f'{current_app.config["EFT_INVOICE_PREFIX"]}{invoice_1.id}'
    assert payment.payment_account_id == payment_account.id
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.payment_method_code == PaymentMethod.EFT.value
    assert payment.invoice_amount == invoice_1_paid
    assert payment.paid_amount == invoice_1_paid

    invoice_reference_1 = invoice_1.references[0]
    assert invoice_reference_1 is not None
    assert invoice_reference_1.invoice_id == invoice_1.id
    assert invoice_reference_1.invoice_number == payment.invoice_number
    assert invoice_reference_1.invoice_number == payment.invoice_number
    assert invoice_reference_1.status_code == InvoiceReferenceStatus.COMPLETED.value

    # Assert details of partially paid invoice
    invoice_2_paid = 150
    assert invoice_2.payment_method_code == PaymentMethod.EFT.value
    assert invoice_2.invoice_status_code == InvoiceStatus.PARTIAL.value
    assert invoice_2.payment_date is not None
    assert invoice_2.payment_date.date() == today
    assert invoice_2.paid == 150
    assert invoice_2.total == 200

    receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_2.id, invoice_2.id)
    assert receipt is not None
    assert receipt.receipt_number == str(invoice_2.id)
    assert receipt.receipt_amount == invoice_2_paid

    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice_2.id)
    assert payment is not None
    assert payment.payment_date.date() == today
    assert payment.invoice_number == f'{current_app.config["EFT_INVOICE_PREFIX"]}{invoice_2.id}'
    assert payment.payment_account_id == payment_account.id
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
    assert payment.payment_method_code == PaymentMethod.EFT.value
    assert payment.invoice_amount == 200
    assert payment.paid_amount == invoice_2_paid

    invoice_reference_2 = invoice_2.references[0]
    assert invoice_reference_2 is not None
    assert invoice_reference_2.invoice_id == invoice_2.id
    assert invoice_reference_2.invoice_number == payment.invoice_number
    assert invoice_reference_2.invoice_number == payment.invoice_number
    assert invoice_reference_2.status_code == InvoiceReferenceStatus.ACTIVE.value
