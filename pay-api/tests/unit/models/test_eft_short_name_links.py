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

"""Tests to assure the EFT Short names model.

Test-Suite to ensure that the EFT Short names model is working as expected.
"""
from datetime import datetime

from pay_api.models.eft_short_names import EFTShortnames as EFTShortnamesModel
from pay_api.models.eft_short_name_links import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.utils.enums import EFTShortnameStatus


def create_short_name_data():
    """Create shortname seed data for test."""
    eft_short_name = EFTShortnamesModel()
    eft_short_name.short_name = 'ABC'
    eft_short_name.save()

    return eft_short_name


def test_eft_short_name_defaults(session):
    """Assert eft short name link defaults are stored."""
    eft_short_name = create_short_name_data()
    eft_short_name_link = EFTShortnameLinksModel()
    eft_short_name_link.eft_short_name_id = eft_short_name.id
    eft_short_name_link.status_code = EFTShortnameStatus.PENDING.value
    eft_short_name_link.auth_account_id = '1234'
    eft_short_name_link.save()

    assert eft_short_name_link.id is not None
    assert eft_short_name_link.eft_short_name_id == eft_short_name.id
    assert eft_short_name_link.created_on.date() == datetime.now().date()
    assert eft_short_name_link.auth_account_id == '1234'
    assert eft_short_name_link.status_code == EFTShortnameStatus.PENDING.value
    assert eft_short_name_link.updated_by is None
    assert eft_short_name_link.updated_by_name is None
    assert eft_short_name_link.updated_on is None


def test_eft_short_name_all_attributes(session):
    """Assert eft short name link defaults are stored."""
    eft_short_name = create_short_name_data()
    eft_short_name_link = EFTShortnameLinksModel()
    eft_short_name_link.eft_short_name_id = eft_short_name.id
    eft_short_name_link.status_code = EFTShortnameStatus.PENDING.value
    eft_short_name_link.auth_account_id = '1234'
    eft_short_name_link.updated_by_name = 'name'
    eft_short_name_link.updated_by = 'userid'
    eft_short_name_link.updated_on = datetime.now()
    eft_short_name_link.save()

    assert eft_short_name_link.id is not None
    assert eft_short_name_link.eft_short_name_id == eft_short_name.id
    assert eft_short_name_link.created_on.date() == datetime.now().date()
    assert eft_short_name_link.auth_account_id == '1234'
    assert eft_short_name_link.status_code == EFTShortnameStatus.PENDING.value
    assert eft_short_name_link.updated_by == 'userid'
    assert eft_short_name_link.updated_by_name == 'name'
    assert eft_short_name_link.updated_on.date() == datetime.now().date()
