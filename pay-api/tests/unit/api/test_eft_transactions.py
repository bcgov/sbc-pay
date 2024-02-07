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
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.utils.enums import EFTFileLineType, EFTProcessStatus, PaymentMethod, Role
from tests.utilities.base_test import (
    factory_eft_file, factory_eft_shortname, factory_payment_account, get_claims, token_header)


def assert_transaction(result_dict: dict, short_name: EFTShortnamesModel, transaction: EFTTransactionModel):
    """Assert short name result."""
    date_format = '%Y-%m-%dT%H:%M:%S'
    assert result_dict['id'] == transaction.id
    assert result_dict['shortNameId'] == short_name.id
    assert result_dict['depositAmount'] == transaction.deposit_amount_cents / 100
    assert datetime.strptime(result_dict['depositDate'], date_format) == transaction.deposit_date
    assert datetime.strptime(result_dict['transactionDate'], date_format) == transaction.transaction_date


def test_search_short_name_transactions(session, client, jwt, app):
    """Assert that EFT short names transactions can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    # create test data
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value,
                                              auth_account_id='1234').save()
    eft_file: EFTFileModel = factory_eft_file()
    short_name_1 = factory_eft_shortname(short_name='TESTSHORTNAME1').save()
    short_name_2 = factory_eft_shortname(short_name='TESTSHORTNAME2', auth_account_id='1234').save()

    # short_name_1 transactions
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
    s2_credit1 = EFTCreditModel(
        eft_file_id=eft_file.id,
        eft_transaction_id=s2_transaction1.id,
        short_name_id=short_name_2.id,
        payment_account_id=payment_account.id,
        amount=302.50,
        remaining_amount=302.50
    ).save()
    s2_credit2 = EFTCreditModel(
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
    assert_transaction(result_dict['items'][0], short_name_1, s1_transaction3)
    assert_transaction(result_dict['items'][1], short_name_1, s1_transaction2)
    assert_transaction(result_dict['items'][2], short_name_1, s1_transaction1)

    # Assert search returns unlinked short names
    rv = client.get(f'/api/v1/eft-shortnames/{short_name_2.id}/transactions', headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict['page'] == 1
    assert result_dict['total'] == 1
    assert result_dict['limit'] == 10
    assert result_dict['items'] is not None
    assert len(result_dict['items']) == 1
    assert result_dict['remainingCredit'] == (s2_credit1.remaining_amount + s2_credit2.remaining_amount)
    assert_transaction(result_dict['items'][0], short_name_2, s2_transaction1)
