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

"""Tests to assure the utilities.

Test-Suite to ensure that the util functions are working as expected.
"""
from datetime import datetime

from pay_api.utils.util import get_nearest_business_day


def test_next_business_day(session):
    """Assert that the get_nearest_business_day is working good."""
    # Jan 1st is Friday ,but a holiday.So assert Monday Jan 4th
    d = datetime(2021, 1, 1)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2021, 1, 4).date()

    # Jan 2nd is Saturday.So assert Monday Jan 4th
    d = datetime(2021, 1, 2)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2021, 1, 4).date()

    # Feb 12 is business day
    d = datetime(2021, 2, 12)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2021, 2, 12).date()

    # Feb 12 is business day and we ask not to include today
    d = datetime(2021, 2, 12)
    business_date = get_nearest_business_day(d, include_today=False)
    assert business_date.date() == datetime(2021, 2, 16).date()

    # assert year end
    d = datetime(2021, 12, 31)
    business_date = get_nearest_business_day(d, include_today=False)
    assert business_date.date() == datetime(2022, 1, 3).date()
