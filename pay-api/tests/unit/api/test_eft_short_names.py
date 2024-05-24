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
from decimal import Decimal

import pytest
from flask import current_app

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import (
    EFTFileLineType, EFTProcessStatus, EFTShortnameStatus, InvoiceStatus, PaymentMethod, PaymentStatus, Role,
    StatementFrequency)
from tests.utilities.base_test import (
    factory_eft_file, factory_eft_shortname, factory_eft_shortname_link, factory_invoice, factory_payment_account,
    factory_statement, factory_statement_invoices, factory_statement_settings, get_claims, token_header)


def test_create_eft_short_name_link(session, client, jwt, app):
    """Assert that an EFT short name link can be created."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value],
                                      username='IDIR/JSMITH'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                            auth_account_id='1234').save()

    short_name = factory_eft_shortname(short_name='TESTSHORTNAME').save()
    rv = client.post(f'/api/v1/eft-shortnames/{short_name.id}/links',
                     data=json.dumps({'accountId': '1234'}),
                     headers=headers)
    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict is not None
    assert link_dict['id'] is not None
    assert link_dict['shortNameId'] == short_name.id
    assert link_dict['statusCode'] == EFTShortnameStatus.PENDING.value
    assert link_dict['accountId'] == '1234'
    assert link_dict['updatedBy'] == 'IDIR/JSMITH'

    date_format = '%Y-%m-%dT%H:%M:%S.%f'
    assert datetime.strptime(link_dict['updatedOn'], date_format).date() == datetime.now().date()


def test_create_eft_short_name_link_validation(session, client, jwt, app):
    """Assert that invalid request is returned for existing short name link."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value],
                                      username='IDIR/JSMITH'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME').save()
    factory_eft_shortname_link(
        short_name_id=short_name.id,
        auth_account_id='1234',
        updated_by='IDIR/JSMITH'
    ).save()

    # Assert requires an auth account id for mapping
    rv = client.post(f'/api/v1/eft-shortnames/{short_name.id}/links',
                     data=json.dumps({}),
                     headers=headers)

    link_dict = rv.json
    assert rv.status_code == 400
    assert link_dict['type'] == 'EFT_SHORT_NAME_ACCOUNT_ID_REQUIRED'

    # Assert cannot create link to an existing mapped account id
    rv = client.post(f'/api/v1/eft-shortnames/{short_name.id}/links',
                     data=json.dumps({'accountId': '1234'}),
                     headers=headers)

    link_dict = rv.json
    assert rv.status_code == 400
    assert link_dict['type'] == 'EFT_SHORT_NAME_ALREADY_MAPPED'


def test_eft_short_name_unlink(session, client, jwt, app):
    """Assert that an EFT short name unlinking and basic state validation."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value],
                                      username='IDIR/JSMITH'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                      auth_account_id='1234').save()

    short_name = factory_eft_shortname(short_name='TESTSHORTNAME').save()
    short_name_link = EFTShortnameLinksModel(
        eft_short_name_id=short_name.id,
        status_code=EFTShortnameStatus.LINKED.value,
        auth_account_id=account.auth_account_id
    ).save()

    # Assert cannot unlink an account not in PENDING status
    rv = client.delete(f'/api/v1/eft-shortnames/{short_name.id}/links/{short_name_link.id}',
                       headers=headers)

    link_dict = rv.json
    assert rv.status_code == 400
    assert link_dict['type'] == 'EFT_SHORT_NAME_LINK_INVALID_STATUS'

    short_name_link.status_code = EFTShortnameStatus.PENDING.value
    short_name_link.save()

    # Assert we can delete a short name link that is pending
    rv = client.delete(f'/api/v1/eft-shortnames/{short_name.id}/links/{short_name_link.id}',
                       headers=headers)
    assert rv.status_code == 202


def test_get_eft_short_name_links(session, client, jwt, app):
    """Assert that short name links can be retrieved."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value],
                                      username='IDIR/JSMITH'), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                      auth_account_id='1234',
                                      name='ABC-123',
                                      branch_name='123').save()
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME').save()

    invoice = factory_invoice(account, payment_method_code=PaymentMethod.EFT.value,
                              total=50, paid=0).save()
    statement_settings = factory_statement_settings(payment_account_id=account.id,
                                                    frequency=StatementFrequency.MONTHLY.value)
    statement = factory_statement(payment_account_id=account.id,
                                  frequency=StatementFrequency.MONTHLY.value,
                                  statement_settings_id=statement_settings.id)
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    # Assert an empty result set is properly returned
    rv = client.get(f'/api/v1/eft-shortnames/{short_name.id}/links',
                    headers=headers)

    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict is not None
    assert link_dict['items'] is not None
    assert len(link_dict['items']) == 0

    # Create a short name link
    rv = client.post(f'/api/v1/eft-shortnames/{short_name.id}/links',
                     data=json.dumps({'accountId': account.auth_account_id}),
                     headers=headers)

    link_dict = rv.json
    assert rv.status_code == 200

    # Assert link is returned in the result
    rv = client.get(f'/api/v1/eft-shortnames/{short_name.id}/links',
                    headers=headers)

    link_list_dict = rv.json
    assert rv.status_code == 200
    assert link_list_dict is not None
    assert link_list_dict['items'] is not None
    assert len(link_list_dict['items']) == 1

    link = link_list_dict['items'][0]
    assert link['accountId'] == account.auth_account_id
    assert link['id'] == link_dict['id']
    assert link['shortNameId'] == short_name.id
    assert link['accountId'] == account.auth_account_id
    assert link['accountName'] == 'ABC'
    assert link['accountBranch'] == '123'
    assert link['amountOwing'] == invoice.total
    assert link['statementId'] == statement.id
    assert link['statusCode'] == EFTShortnameStatus.PENDING.value
    assert link['updatedBy'] == 'IDIR/JSMITH'


def assert_short_name_summary(result_dict: dict,
                              short_name: EFTShortnamesModel,
                              transaction: EFTTransactionModel,
                              expected_credits_remaining: Decimal,
                              expected_linked_accounts_count: int):
    """Assert short name summary result."""
    date_format = '%Y-%m-%dT%H:%M:%S'
    assert result_dict['id'] == short_name.id
    assert result_dict['shortName'] == short_name.short_name
    assert result_dict['creditsRemaining'] == expected_credits_remaining
    assert result_dict['linkedAccountsCount'] == expected_linked_accounts_count
    assert datetime.strptime(result_dict['lastPaymentReceivedDate'], date_format) == transaction.deposit_date


def test_eft_short_name_summaries(session, client, jwt, app):
    """Assert that EFT short names summaries can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Assert initial search returns empty items
    rv = client.get('/api/v1/eft-shortnames/summaries', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 0

    # create test data
    factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                            auth_account_id='1234',
                            name='ABC-123',
                            branch_name='123').save()

    short_name_1, s1_transaction1, short_name_2, s2_transaction1 = create_eft_summary_search_data()

    # Assert short name search brings back both short names
    rv = client.get('/api/v1/eft-shortnames/summaries?shortName=SHORT', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 2
    assert_short_name_summary(result_dict['items'][0],
                              short_name_1, s1_transaction1, 204.0, 0)
    assert_short_name_summary(result_dict['items'][1],
                              short_name_2, s2_transaction1, 302.5, 1)

    # Assert short name search brings back first short name
    rv = client.get('/api/v1/eft-shortnames/summaries?shortName=name1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_1, s1_transaction1, 204.0, 0)

    # Assert search linked accounts count
    rv = client.get('/api/v1/eft-shortnames/summaries?linkedAccountsCount=0', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_1, s1_transaction1, 204.0, 0)

    rv = client.get('/api/v1/eft-shortnames/summaries?linkedAccountsCount=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_2, s2_transaction1, 302.5, 1)

    # Assert search by payment received date
    rv = client.get('/api/v1/eft-shortnames/summaries?'
                    'paymentReceivedStartDate=2024-01-16&paymentReceivedEndDate=2024-01-16', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_2, s2_transaction1, 302.5, 1)

    # Assert search by short name id
    rv = client.get(f'/api/v1/eft-shortnames/summaries?shortNameId={short_name_2.id}', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_2, s2_transaction1, 302.5, 1)

    # Assert search by remaining credits
    rv = client.get('/api/v1/eft-shortnames/summaries?creditsRemaining=204', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_1, s1_transaction1, 204.0, 0)

    # Assert search query by no state will return all records
    rv = client.get('/api/v1/eft-shortnames/summaries', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 2
    assert_short_name_summary(result_dict['items'][0],
                              short_name_1, s1_transaction1, 204.0, 0)
    assert_short_name_summary(result_dict['items'][1],
                              short_name_2, s2_transaction1, 302.5, 1)

    # Assert search pagination - page 1 works
    rv = client.get('/api/v1/eft-shortnames/summaries?page=1&limit=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 1
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_1, s1_transaction1, 204.0, 0)

    # Assert search pagination - page 2 works
    rv = client.get('/api/v1/eft-shortnames/summaries?page=2&limit=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 2
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 2
    assert result_dict['limit'] == 1
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name_summary(result_dict['items'][0],
                              short_name_2, s2_transaction1, 302.5, 1)


def create_eft_summary_search_data():
    """Create seed data for EFT summary searches."""
    eft_file: EFTFileModel = factory_eft_file()
    short_name_1 = factory_eft_shortname(short_name='TESTSHORTNAME1').save()
    short_name_2 = factory_eft_shortname(short_name='TESTSHORTNAME2').save()
    factory_eft_shortname_link(
        short_name_id=short_name_2.id,
        auth_account_id='1234',
        updated_by='IDIR/JSMITH'
    ).save()

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

    EFTCreditModel(eft_file_id=eft_file.id,
                   short_name_id=s1_transaction1.short_name_id,
                   amount=s1_transaction1.deposit_amount_cents / 100,
                   remaining_amount=s1_transaction1.deposit_amount_cents / 100
                   ).save()

    # Identical to transaction 1 should not return duplicate short name rows - partitioned by transaction date, id
    s1_transaction2: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 2, 30),
        deposit_date=datetime(2024, 1, 6, 10, 5),
        deposit_amount_cents=10250,
        short_name_id=short_name_1.id

    ).save()

    EFTCreditModel(eft_file_id=eft_file.id,
                   short_name_id=s1_transaction2.short_name_id,
                   amount=s1_transaction2.deposit_amount_cents / 100,
                   remaining_amount=s1_transaction2.deposit_amount_cents / 100
                   ).save()

    EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 10, 2, 30),
        deposit_date=datetime(2024, 1, 5, 10, 5),
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

    EFTCreditModel(eft_file_id=eft_file.id,
                   short_name_id=s2_transaction1.short_name_id,
                   amount=s2_transaction1.deposit_amount_cents / 100,
                   remaining_amount=s2_transaction1.deposit_amount_cents / 100
                   ).save()

    return short_name_1, s1_transaction1, short_name_2, s2_transaction1


def create_eft_search_data():
    """Create seed data for EFT searches."""
    payment_account_1 = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                                auth_account_id='1111',
                                                name='ABC-1111',
                                                branch_name='111').save()
    payment_account_2 = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                                auth_account_id='2222',
                                                name='DEF-2222',
                                                branch_name='222').save()
    payment_account_3 = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                                auth_account_id='3333',
                                                name='GHI-3333',
                                                branch_name='333').save()

    # Create unlinked short name
    short_name_unlinked = factory_eft_shortname(short_name='TESTSHORTNAME1').save()

    # Create single linked short name
    short_name_linked = factory_eft_shortname(short_name='TESTSHORTNAME2').save()
    factory_eft_shortname_link(
        short_name_id=short_name_linked.id,
        auth_account_id=payment_account_1.auth_account_id,
        updated_by='IDIR/JSMITH'
    ).save()
    # Create statement with multiple invoices
    s1_invoice_1 = factory_invoice(payment_account_1, payment_method_code=PaymentMethod.EFT.value,
                                   total=50, paid=0).save()
    s1_invoice_2 = factory_invoice(payment_account_1, payment_method_code=PaymentMethod.EFT.value,
                                   total=100.50, paid=0).save()
    s1_settings = factory_statement_settings(payment_account_id=payment_account_1.id,
                                             frequency=StatementFrequency.MONTHLY.value)
    statement_1 = factory_statement(payment_account_id=payment_account_1.id,
                                    frequency=StatementFrequency.MONTHLY.value,
                                    statement_settings_id=s1_settings.id)
    factory_statement_invoices(statement_id=statement_1.id, invoice_id=s1_invoice_1.id)
    factory_statement_invoices(statement_id=statement_1.id, invoice_id=s1_invoice_2.id)

    # Create multi account linked short name
    short_name_multi_linked = factory_eft_shortname(short_name='TESTSHORTNAME3').save()
    factory_eft_shortname_link(
        short_name_id=short_name_multi_linked.id,
        auth_account_id=payment_account_2.auth_account_id,
        updated_by='IDIR/JSMITH'
    ).save()
    factory_eft_shortname_link(
        short_name_id=short_name_multi_linked.id,
        auth_account_id=payment_account_3.auth_account_id,
        updated_by='IDIR/JSMITH'
    ).save()

    s2_settings = factory_statement_settings(payment_account_id=payment_account_2.id,
                                             frequency=StatementFrequency.MONTHLY.value)
    statement_2 = factory_statement(payment_account_id=payment_account_2.id,
                                    frequency=StatementFrequency.MONTHLY.value,
                                    statement_settings_id=s2_settings.id)

    s3_settings = factory_statement_settings(payment_account_id=payment_account_3.id,
                                             frequency=StatementFrequency.MONTHLY.value)
    statement_3 = factory_statement(payment_account_id=payment_account_3.id,
                                    frequency=StatementFrequency.MONTHLY.value,
                                    statement_settings_id=s3_settings.id)
    s3_invoice_1 = factory_invoice(payment_account_3, payment_method_code=PaymentMethod.EFT.value,
                                   total=33.33, paid=0).save()
    factory_statement_invoices(statement_id=statement_3.id, invoice_id=s3_invoice_1.id)

    return {
        'single-linked': {'short_name': short_name_linked,
                          'accounts': [payment_account_1],
                          'statement_summary': [{'statement_id': statement_1.id, 'owing_amount': 150.50}]},
        'multi-linked': {'short_name': short_name_multi_linked,
                         'accounts': [payment_account_2, payment_account_3],
                         'statement_summary': [{'statement_id': statement_2.id, 'owing_amount': 0},
                                               {'statement_id': statement_3.id, 'owing_amount': 33.33}]},
        'unlinked': {'short_name': short_name_unlinked,
                     'accounts': [],
                     'statement_summary': None}
    }


def assert_short_name(result_dict: dict, short_name: EFTShortnamesModel,
                      payment_account: PaymentAccountModel = None,
                      statement_summary=None):
    """Assert short name result."""
    assert result_dict['shortName'] == short_name.short_name

    if not payment_account:
        assert result_dict['accountId'] is None
        assert result_dict['accountName'] is None
        assert result_dict['accountBranch'] is None
    else:
        assert result_dict['accountId'] == payment_account.auth_account_id
        assert payment_account.name.startswith(result_dict['accountName'])
        assert result_dict['accountBranch'] == payment_account.branch_name

    if not statement_summary:
        assert result_dict['amountOwing'] == 0
        assert result_dict['statementId'] is None
    else:
        assert result_dict['amountOwing'] == statement_summary['owing_amount']
        assert result_dict['statementId'] == statement_summary['statement_id']


def test_search_eft_short_names(session, client, jwt, app):
    """Assert that EFT short names can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # Assert initial search returns empty items
    rv = client.get('/api/v1/eft-shortnames', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 0

    # create test data
    data_dict = create_eft_search_data()

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
    assert_short_name(result_dict['items'][0], data_dict['unlinked']['short_name'])

    # Assert search returns linked short names with payment account name that has a branch
    rv = client.get('/api/v1/eft-shortnames?state=LINKED', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 3
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 3
    assert_short_name(result_dict['items'][0],
                      data_dict['single-linked']['short_name'],
                      data_dict['single-linked']['accounts'][0],
                      data_dict['single-linked']['statement_summary'][0])
    assert_short_name(result_dict['items'][1],
                      data_dict['multi-linked']['short_name'],
                      data_dict['multi-linked']['accounts'][0],
                      data_dict['multi-linked']['statement_summary'][0])
    assert_short_name(result_dict['items'][2],
                      data_dict['multi-linked']['short_name'],
                      data_dict['multi-linked']['accounts'][1],
                      data_dict['multi-linked']['statement_summary'][1])

    # Assert search account name
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountName=BC', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0],
                      data_dict['single-linked']['short_name'],
                      data_dict['single-linked']['accounts'][0],
                      data_dict['single-linked']['statement_summary'][0])

    # Assert search account branch
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountBranch=2', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0],
                      data_dict['multi-linked']['short_name'],
                      data_dict['multi-linked']['accounts'][0],
                      data_dict['multi-linked']['statement_summary'][0])

    # Assert search query by no state will return all records
    rv = client.get('/api/v1/eft-shortnames', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 3
    assert result_dict['total'] == 4
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 4
    assert_short_name(result_dict['items'][0],
                      data_dict['unlinked']['short_name'])
    assert_short_name(result_dict['items'][1],
                      data_dict['single-linked']['short_name'],
                      data_dict['single-linked']['accounts'][0],
                      data_dict['single-linked']['statement_summary'][0])
    assert_short_name(result_dict['items'][2],
                      data_dict['multi-linked']['short_name'],
                      data_dict['multi-linked']['accounts'][0],
                      data_dict['multi-linked']['statement_summary'][0])
    assert_short_name(result_dict['items'][3],
                      data_dict['multi-linked']['short_name'],
                      data_dict['multi-linked']['accounts'][1],
                      data_dict['multi-linked']['statement_summary'][1])

    # Assert search pagination - page 1 works
    rv = client.get('/api/v1/eft-shortnames?page=1&limit=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 3
    assert result_dict['total'] == 4
    assert result_dict['limit'] == 1
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0],
                      data_dict['unlinked']['short_name'])

    # Assert search pagination - page 2 works
    rv = client.get('/api/v1/eft-shortnames?page=2&limit=1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 2
    assert result_dict['stateTotal'] == 3
    assert result_dict['total'] == 4
    assert result_dict['limit'] == 1
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0],
                      data_dict['single-linked']['short_name'],
                      data_dict['single-linked']['accounts'][0],
                      data_dict['single-linked']['statement_summary'][0])

    # Assert search text brings back one short name
    rv = client.get('/api/v1/eft-shortnames?shortName=name1', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 3
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0],
                      data_dict['unlinked']['short_name'])

    # Assert search account id
    rv = client.get('/api/v1/eft-shortnames?state=LINKED&accountId=1111', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['stateTotal'] == 2
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert_short_name(result_dict['items'][0],
                      data_dict['single-linked']['short_name'],
                      data_dict['single-linked']['accounts'][0],
                      data_dict['single-linked']['statement_summary'][0])


@pytest.mark.skip(reason='This needs to be re-thought, the create cfs invoice job should be handling receipt creation'
                         'and creating invoice references when payments are mapped, '
                         'it should wait until 6 pm before marking invoices as PAID'
                         'Otherwise calls to CFS could potentially fail and the two systems would go out of sync.')
def test_apply_eft_short_name_credits(session, client, jwt, app):
    """Assert that credits are applied to invoices when short name is mapped to an account."""
    token = jwt.create_jwt(get_claims(roles=[Role.STAFF.value, Role.MANAGE_EFT.value]), token_header)
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

    assert not invoice_1.references

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

    assert not invoice_2.references
