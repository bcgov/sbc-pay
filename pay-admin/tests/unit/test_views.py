# Copyright © 2019 Province of British Columbia
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
"""Test Views.

Test Views module.
"""

import pytest

from admin.views.code import CodeConfig
from admin.views.corp_type import CorpType, CorpTypeConfig
from admin.views.distribution_code import DistributionCode, DistributionCodeConfig
from admin.views.fee_code import FeeCode, FeeCodeConfig
from admin.views.fee_schedule import FeeSchedule, FeeScheduleConfig
from pay_api.models import FilingType


@pytest.mark.parametrize(
    "model, config",
    [
        (FeeCode, FeeCodeConfig),
        (CorpType, CorpTypeConfig),
        (FilingType, CodeConfig),
        (DistributionCode, DistributionCodeConfig),
        (FeeSchedule, FeeScheduleConfig),
    ],
)
def test_view_configs(db, model, config):
    """Test view configs."""
    view = config(model, db.session)
    columns = view.get_list_columns()

    for col in columns:
        assert col[0] in config.column_list
