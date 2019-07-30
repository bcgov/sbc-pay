# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests to assure the Status check service layer.

Test-Suite to ensure that the Status Service layer is working as expected.
"""
from datetime import datetime
from unittest.mock import patch

import pytz

from pay_api.services.status_service import StatusService


def test_get_schedules_with_name(app):
    """Assert that the function returns schedules."""
    with app.app_context():
        service_name = 'PAYBC'

        get_response = StatusService().get_schedules(service_name=service_name)
        assert get_response[0]['up'] is not None


def test_get_schedules_without_name(app):
    """Assert that the function don't return schedules."""
    with app.app_context():
        get_response = StatusService().get_schedules(service_name=None)
        assert get_response is None


def test_get_schedules_with_name_not_exists(app):
    """Assert that the function don't return schedules."""
    with app.app_context():
        service_name = 'PAYBC1'

        get_response = StatusService().get_schedules(service_name=service_name)
        assert get_response is None


def test_status_check_without_name(app):
    """Assert that the function returns schedules."""
    with app.app_context():
        service_name = None

        get_response = StatusService().schedule_status(service_name=service_name)

        assert get_response is not None
        assert get_response['service'] == service_name
        assert get_response['current_status'] == 'None'


def test_status_check_no_schedule(app):
    """Assert that the function return no schedule."""
    # sunday 6:30am - 9:30pm
    schedule_json = [{}]

    with app.app_context():
        service_name = 'PAYBC'

        mock_get_schedule = patch('pay_api.services.status_service.StatusService.get_schedules')

        mock_get = mock_get_schedule.start()
        mock_get.return_value = schedule_json

        get_response = StatusService().schedule_status(service_name=service_name)

        mock_get.stop()

        assert get_response is not None
        assert get_response['service'] == service_name
        assert get_response['current_status']
        assert get_response['next_schedule_date'] is None


def test_status_check_status_false(app):
    """Assert that the function return a valid schedule."""
    # Sunday 6:30am - 9:30pm
    schedule_json = [{'up': '30 6 * * 7', 'down': '30 21 * * 7'}]

    # 2019-07-30 10:30pm Sunday
    check_date: datetime = datetime(1988, 7, 31, 22, 30)

    with app.app_context():
        service_name = 'PAYBC'

        mock_get_schedule = patch('pay_api.services.status_service.StatusService.get_schedules')

        mock_get = mock_get_schedule.start()
        mock_get.return_value = schedule_json

        get_response = StatusService().schedule_status(service_name=service_name, check_date=check_date)

        mock_get.stop()

        assert get_response is not None
        assert get_response['service'] == service_name
        assert not get_response['current_status']
        timezone = pytz.timezone('US/Pacific')
        assert get_response['next_schedule_date'] == timezone.localize(datetime(1988, 7, 31, 21, 30))


def test_status_check_single_schedule(app):
    """Assert that the function return a valid schedule."""
    # Sunday 6:30am - 9:30pm
    schedule_json = [{'up': '30 6 * * 7', 'down': '30 21 * * 7'}]

    # 2019-07-30 11:30am Saturday
    check_date: datetime = datetime(1988, 7, 30, 11, 30)

    with app.app_context():
        service_name = 'PAYBC'

        mock_get_schedule = patch('pay_api.services.status_service.StatusService.get_schedules')

        mock_get = mock_get_schedule.start()
        mock_get.return_value = schedule_json

        get_response = StatusService().schedule_status(service_name=service_name, check_date=check_date)

        mock_get.stop()

        assert get_response is not None
        assert get_response['service'] == service_name
        assert get_response['current_status']
        timezone = pytz.timezone('US/Pacific')
        assert get_response['next_schedule_date'] == timezone.localize(datetime(1988, 7, 31, 21, 30))


def test_status_check_multiple_schedule(app):
    """Assert that the function don't return schedules."""
    # Saturday 6:30am - 9:30pm, Sunday 6:30am - 9:30pm
    schedule_json = [{'up': '30 6 * * 6', 'down': '30 21 * * 6'}, {'up': '30 6 * * 7', 'down': '30 21 * * 7'}]

    # 1988-07-30 11:30am Saturday
    check_date: datetime = datetime(1988, 7, 30, 11, 30)

    with app.app_context():
        service_name = 'PAYBC'

        mock_get_schedule = patch('pay_api.services.status_service.StatusService.get_schedules')

        mock_get = mock_get_schedule.start()
        mock_get.return_value = schedule_json

        get_response = StatusService().schedule_status(service_name=service_name, check_date=check_date)

        mock_get.stop()

        assert get_response is not None
        assert get_response['service'] == service_name
        assert get_response['current_status']
        timezone = pytz.timezone('US/Pacific')
        assert get_response['next_schedule_date'] == timezone.localize(datetime(1988, 7, 30, 21, 30))


def test_status_check_multiple_flexible_schedule(app):
    """Assert that the function don't return schedules."""
    # Monday - Wedensday 6:30am - 9:30pm
    # Thursday 6:30am -
    # Friday - 9:30pm
    # Saturday 6:30am - 9:30pm
    # Sunday 6:30am - 9:30pm
    schedule_json = [
        {'up': '30 6 * * 1-3', 'down': '30 21 * * 1-3'},
        {'up': '30 6 * * 4', 'down': '30 21 * * 4'},
        {'down': '30 21 * * 5'},
        {'up': '30 6 * * 6', 'down': '30 21 * * 6'},
        {'up': '30 6 * * 7', 'down': '30 21 * * 7'},
    ]

    # 1988-07-28 11:30am Saturday
    check_date: datetime = datetime(1988, 7, 28, 11, 30)

    with app.app_context():
        service_name = 'PAYBC'

        mock_get_schedule = patch('pay_api.services.status_service.StatusService.get_schedules')

        mock_get = mock_get_schedule.start()
        mock_get.return_value = schedule_json

        get_response = StatusService().schedule_status(service_name=service_name, check_date=check_date)

        assert get_response is not None
        assert get_response['service'] == service_name
        assert get_response['current_status']
        timezone = pytz.timezone('US/Pacific')
        assert get_response['next_schedule_date'] == timezone.localize(datetime(1988, 7, 28, 21, 30))


def test_status_check_multiple_flexible_schedule_false(app):
    """Assert that the function don't return schedules."""
    # Monday - Wedensday 6:30am - 9:30pm
    # Thursday 6:30am -
    # Friday - 9:30pm
    # Saturday 6:30am - 9:30pm
    # Sunday 6:30am - 9:30pm
    schedule_json = [
        {'up': '30 6 * * 1-3', 'down': '30 21 * * 1-3'},
        {'up': '30 6 * * 4', 'down': '30 21 * * 4'},
        {'down': '30 21 * * 5'},
        {'up': '30 6 * * 6', 'down': '30 21 * * 6'},
        {'up': '30 6 * * 7', 'down': '30 21 * * 7'},
    ]

    # 1988-07-29 11:30pm Friday
    check_date: datetime = datetime(1988, 7, 29, 23, 30)

    with app.app_context():
        service_name = 'PAYBC'

        mock_get_schedule = patch('pay_api.services.status_service.StatusService.get_schedules')

        mock_get = mock_get_schedule.start()
        mock_get.return_value = schedule_json

        get_response = StatusService().schedule_status(service_name=service_name, check_date=check_date)

        assert get_response is not None
        assert get_response['service'] == service_name
        assert get_response['current_status']
        timezone = pytz.timezone('US/Pacific')
        assert get_response['next_schedule_date'] == timezone.localize(datetime(1988, 7, 29, 21, 30))
