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

"""Tests to assure the EFT short names history end-point.

Test-Suite to ensure that the /eft-shortnames/{id}/history endpoint is working as expected.
"""

from pay_api.services.eft_short_name_historical import EFTShortnameHistorical as EFTHistoryService
from pay_api.services.eft_short_name_historical import EFTShortnameHistory as EFTHistory
from pay_api.utils.enums import EFTHistoricalTypes, PaymentMethod, Role
from tests.utilities.base_test import factory_eft_shortname, factory_payment_account, get_claims, token_header


def setup_test_data():
    """Set up eft short name historical data."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                              auth_account_id='1234', name='ABC-BRANCH', branch_name='BRANCH').save()
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME1').save()

    EFTHistoryService.create_funds_received(EFTHistory(short_name_id=short_name.id,
                                                       amount=351.50,
                                                       credit_balance=351.50)).save()

    EFTHistoryService.create_statement_paid(EFTHistory(short_name_id=short_name.id,
                                                       amount=351.50,
                                                       credit_balance=0,
                                                       payment_account_id=payment_account.id,
                                                       related_group_link_id=1,
                                                       statement_number=1234)).save()

    EFTHistoryService.create_statement_reverse(EFTHistory(short_name_id=short_name.id,
                                                          amount=351.50,
                                                          credit_balance=351.50,
                                                          payment_account_id=payment_account.id,
                                                          related_group_link_id=2,
                                                          statement_number=1234)).save()

    return payment_account, short_name


def test_search_short_name_history(session, client, jwt, app):
    """Assert that EFT short names history can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payment_account, short_name = setup_test_data()
    rv = client.get(f'/api/v1/eft-shortnames/{short_name.id}/history', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['total'] == 3
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 3

    transaction_date = EFTHistoryService.transaction_date_now().strftime('%Y-%m-%d')
    funds_received = result_dict['items'][2]
    assert not funds_received['isReversible'] is True
    assert funds_received['accountBranch'] is None
    assert funds_received['accountId'] is None
    assert funds_received['accountName'] is None
    assert funds_received['amount'] == 351.50
    assert funds_received['historicalId'] is not None
    assert funds_received['shortNameBalance'] == 351.50
    assert funds_received['shortNameId'] == short_name.id
    assert funds_received['statementNumber'] is None
    assert funds_received['transactionType'] == EFTHistoricalTypes.FUNDS_RECEIVED.value
    assert funds_received['transactionDate'] == transaction_date
    assert funds_received['transactionDescription'] == 'Funds Received'

    statement_paid = result_dict['items'][1]
    assert statement_paid['isReversible'] is True
    assert statement_paid['accountBranch'] == payment_account.branch_name
    assert statement_paid['accountId'] == payment_account.auth_account_id
    assert statement_paid['accountName'] == 'ABC'
    assert statement_paid['amount'] == 351.50
    assert statement_paid['historicalId'] is not None
    assert statement_paid['shortNameBalance'] == 0
    assert statement_paid['shortNameId'] == short_name.id
    assert statement_paid['statementNumber'] == 1234
    assert statement_paid['transactionType'] == EFTHistoricalTypes.STATEMENT_PAID.value
    assert statement_paid['transactionDate'] == transaction_date
    assert statement_paid['transactionDescription'] == 'Statement Paid'

    statement_reverse = result_dict['items'][0]
    assert statement_reverse['isReversible'] is False
    assert statement_reverse['accountBranch'] == payment_account.branch_name
    assert statement_reverse['accountId'] == payment_account.auth_account_id
    assert statement_reverse['accountName'] == 'ABC'
    assert statement_reverse['amount'] == 351.50
    assert statement_reverse['historicalId'] is not None
    assert statement_reverse['shortNameBalance'] == 351.50
    assert statement_reverse['shortNameId'] == short_name.id
    assert statement_reverse['statementNumber'] == 1234
    assert statement_reverse['transactionType'] == EFTHistoricalTypes.STATEMENT_REVERSE.value
    assert statement_reverse['transactionDate'] == transaction_date
    assert statement_reverse['transactionDescription'] == 'Payment Reversed'
