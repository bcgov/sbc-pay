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


def test_eft_short_name_defaults(session):
    """Assert eft short names defaults are stored."""
    eft_short_name = EFTShortnamesModel()
    eft_short_name.short_name = 'ABC'
    eft_short_name.save()

    assert eft_short_name.id is not None
    assert eft_short_name.short_name == 'ABC'
    assert eft_short_name.created_on.date() == datetime.now().date()
    assert eft_short_name.auth_account_id is None


def test_eft_short_names_all_attributes(session):
    """Assert all eft short names attributes are stored."""
    eft_short_name = EFTShortnamesModel()
    eft_short_name.short_name = 'ABC'
    eft_short_name.auth_account_id = '1234'
    eft_short_name.save()

    assert eft_short_name.id is not None

    eft_short_name = EFTShortnamesModel.find_by_id(eft_short_name.id)
    assert eft_short_name.short_name == 'ABC'
    assert eft_short_name.auth_account_id == '1234'
    assert eft_short_name.created_on.date() == datetime.now().date()
