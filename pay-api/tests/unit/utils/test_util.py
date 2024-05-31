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

"""Tests to assure the utilities.

Test-Suite to ensure that the util functions are working as expected.
"""
from holidays.constants import GOVERNMENT, OPTIONAL, PUBLIC
from holidays.countries import Canada
from datetime import datetime

from pay_api.utils.util import get_nearest_business_day
from pay_api.schemas import utils as schema_utils


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
    # Observed holiday on the 3rd of January
    assert business_date.date() == datetime(2022, 1, 4).date()

    # Christmas - over boxing day.
    d = datetime(2023, 12, 25)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 12, 27).date()

    # Easter Monday
    d = datetime(2023, 4, 10)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 4, 11).date()

    # Labour Day
    d = datetime(2023, 9, 4)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 9, 5).date()

    # Sat before - Family Day (Monday Feb 20, 2023)
    d = datetime(2023, 2, 18)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 2, 21).date()

    # Truth and reconciliation day: Tuesday Sept 30, 2025
    d = datetime(2025, 9, 30)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2025, 10, 1).date()

    # Truth and reconciliation day: Saturday Sept 30, 2023, Holiday observed on 2nd
    d = datetime(2023, 9, 30)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 10, 3).date()

    # Weekday check - Friday December 1st, 2023
    d = datetime(2023, 12, 1)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 12, 1).date()

    # Weekend check - Saturday December 2nd, 2023
    d = datetime(2023, 12, 2)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 12, 4).date()

    # Weekend check - Sunday December 3rd, 2023
    d = datetime(2023, 12, 3)
    business_date = get_nearest_business_day(d)
    assert business_date.date() == datetime(2023, 12, 4).date()


def test_print_holidays():
    """Print holidays, can be used to take a quick peak at the holidays."""
    holidays = Canada(subdiv='BC', observed=True, categories=(GOVERNMENT, OPTIONAL, PUBLIC), years=2023)
    holidays._add_easter_monday('Easter Monday')  # pylint: disable=protected-access
    for date, name in sorted(holidays.items()):
        print(date, name)
    assert True


def test_validate_schema():
    """Assert get_schema works."""
    schema_utils.get_schema('transaction_request.json')
    assert True
