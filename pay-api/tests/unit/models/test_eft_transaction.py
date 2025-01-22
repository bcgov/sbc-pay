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

"""Tests to assure the EFT Transaction model.

Test-Suite to ensure that the EFT Transaction model is working as expected.
"""
from datetime import datetime, timezone

from pay_api.models import db
from pay_api.models.eft_file import EFTFile as EFTFileModel
from pay_api.models.eft_transaction import EFTTransaction as EFTTransactionModel
from pay_api.utils.enums import EFTFileLineType, EFTProcessStatus


def test_eft_transaction_defaults(session):
    """Assert eft transaction defaults are stored."""
    eft_file = EFTFileModel()
    eft_file.file_ref = "test.txt"
    eft_file.save()

    assert eft_file.id is not None

    eft_transaction = EFTTransactionModel()
    eft_transaction.file_id = eft_file.id
    eft_transaction.line_number = 1
    eft_transaction.line_type = EFTFileLineType.HEADER.value
    eft_transaction.status_code = EFTProcessStatus.FAILED.value
    eft_transaction.save()

    eft_transaction = (
        db.session.query(EFTTransactionModel).filter(EFTTransactionModel.id == eft_transaction.id).one_or_none()
    )

    assert eft_transaction.id is not None
    assert eft_transaction.created_on is not None
    assert eft_transaction.last_updated_on is not None
    assert eft_transaction.created_on.replace(microsecond=0) == eft_transaction.last_updated_on.replace(microsecond=0)
    assert eft_transaction.status_code == EFTProcessStatus.FAILED.value
    assert eft_transaction.file_id == eft_file.id
    assert eft_transaction.line_number == 1
    assert eft_transaction.line_type == EFTFileLineType.HEADER.value
    assert eft_transaction.deposit_date is None
    assert eft_transaction.transaction_date is None


def test_eft_file_all_attributes(session):
    """Assert all eft transaction attributes are stored."""
    eft_file = EFTFileModel()
    eft_file.file_ref = "test.txt"
    eft_file.save()

    assert eft_file.id is not None

    completed_on = datetime(2023, 9, 30, 10, 0)
    deposit_date = datetime(2023, 9, 28, 10, 0, tzinfo=timezone.utc)
    transaction_date = datetime(2023, 9, 29, 10, 0, tzinfo=timezone.utc)
    error_messages = ["message 1", "message 2"]
    batch_number = "123456789"
    jv_type = "I"
    jv_number = "5678910"
    sequence_number = "001"

    eft_transaction = EFTTransactionModel()
    eft_transaction.file_id = eft_file.id
    eft_transaction.batch_number = batch_number
    eft_transaction.sequence_number = sequence_number
    eft_transaction.jv_type = jv_type
    eft_transaction.jv_number = jv_number
    eft_transaction.line_number = 2
    eft_transaction.line_type = EFTFileLineType.TRANSACTION.value
    eft_transaction.status_code = EFTProcessStatus.COMPLETED.value
    eft_transaction.completed_on = completed_on
    eft_transaction.transaction_date = transaction_date
    eft_transaction.deposit_date = deposit_date
    eft_transaction.error_messages = error_messages
    eft_transaction.save()

    assert eft_transaction.id is not None

    eft_transaction = eft_transaction.find_by_id(eft_transaction.id)

    assert eft_transaction is not None
    assert eft_transaction.created_on is not None
    assert eft_transaction.last_updated_on is not None
    assert eft_transaction.created_on.replace(microsecond=0) == eft_transaction.last_updated_on.replace(microsecond=0)
    assert eft_transaction.status_code == EFTProcessStatus.COMPLETED.value
    assert eft_transaction.file_id == eft_file.id
    assert eft_transaction.sequence_number == sequence_number
    assert eft_transaction.batch_number == batch_number
    assert eft_transaction.jv_type == jv_type
    assert eft_transaction.jv_number == jv_number
    assert eft_transaction.line_number == 2
    assert eft_transaction.line_type == EFTFileLineType.TRANSACTION.value
    assert eft_transaction.completed_on == completed_on
    assert eft_transaction.transaction_date == transaction_date
    assert eft_transaction.deposit_date == deposit_date
    assert eft_transaction.error_messages == error_messages
    assert eft_transaction.error_messages[0] == "message 1"
    assert eft_transaction.error_messages[1] == "message 2"
