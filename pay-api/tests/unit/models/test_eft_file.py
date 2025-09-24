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

"""Tests to assure the EFT File model.

Test-Suite to ensure that the EFT File model is working as expected.
"""

from datetime import datetime

from pay_api.models.eft_file import EFTFile as EFTFileModel
from pay_api.utils.enums import EFTProcessStatus


def test_eft_file_defaults(session):
    """Assert eft file defaults are stored."""
    eft_file = EFTFileModel()
    eft_file.file_ref = "test.txt"
    eft_file.save()

    assert eft_file.id is not None
    assert eft_file.created_on is not None
    assert eft_file.status_code == EFTProcessStatus.IN_PROGRESS.value


def test_eft_file_all_attributes(session):
    """Assert all eft file attributes are stored."""
    eft_file = EFTFileModel()

    file_creation = datetime(2023, 9, 30, 1, 0)
    created_on = datetime(2023, 9, 30, 10, 0)
    completed_on = datetime(2023, 9, 30, 11, 0)
    deposit_from_date = datetime(2023, 9, 28)
    deposit_to_date = datetime(2023, 9, 29)
    number_of_details = 10
    total_deposit_cents = 125000

    eft_file.file_creation_date = file_creation
    eft_file.created_on = created_on
    eft_file.completed_on = completed_on
    eft_file.deposit_from_date = deposit_from_date
    eft_file.deposit_to_date = deposit_to_date
    eft_file.number_of_details = number_of_details
    eft_file.total_deposit_cents = total_deposit_cents
    eft_file.file_ref = "test.txt"
    eft_file.status_code = EFTProcessStatus.COMPLETED.value
    eft_file.save()

    assert eft_file.id is not None
    eft_file = EFTFileModel.find_by_id(eft_file.id)

    assert eft_file is not None
    assert eft_file.status_code == EFTProcessStatus.COMPLETED.value
    assert eft_file.file_creation_date == file_creation
    assert eft_file.created_on == created_on
    assert eft_file.completed_on == completed_on
    assert eft_file.deposit_from_date == deposit_from_date
    assert eft_file.deposit_to_date == deposit_to_date
    assert eft_file.number_of_details == number_of_details
    assert eft_file.total_deposit_cents == total_deposit_cents
    assert eft_file.file_ref == "test.txt"
