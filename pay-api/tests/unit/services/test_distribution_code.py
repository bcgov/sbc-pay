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

"""Tests to assure the Distribution code Service.

Test-Suite to ensure that the Distribution code Service is working as expected.
"""

from pay_api import services
from tests.utilities.base_test import get_distribution_code_payload


def test_distribution_code_saved_from_new(session, public_user_mock):
    """Assert that the fee schedule is saved to the table."""
    distribution_code_svc = services.DistributionCode()
    distribution_code = distribution_code_svc.save_or_update(get_distribution_code_payload())
    assert distribution_code is not None
    assert distribution_code.get('client') == '100'


def test_create_distribution_to_fee_link(session, public_user_mock):
    """Assert that the fee schedule is saved to the table."""
    distribution_code_svc = services.DistributionCode()
    distribution_code = distribution_code_svc.save_or_update(get_distribution_code_payload())
    assert distribution_code is not None
    distribution_id = distribution_code.get('distributionCodeId')

    distribution_code_svc.create_link([
        {
            'feeScheduleId': 1
        },
        {
            'feeScheduleId': 2
        },
        {
            'feeScheduleId': 3
        }
    ], distribution_id)

    schedules = distribution_code_svc.find_fee_schedules_by_distribution_id(distribution_id)
    assert len(schedules.get('items')) == 3
