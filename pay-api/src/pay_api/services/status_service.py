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
"""Service to check status of service(s)."""
import json
from datetime import date, datetime, timedelta

import pytz
from croniter import croniter
from flask import current_app


class StatusService:
    """Service to check status of service(s)."""

    def schedule_status(self, service_name: str, check_date: datetime = datetime.utcnow()):
        """Check service scheduled status . The check date should be UTC datetime format. """
        current_status: str = 'None'
        up_dates: list = list()
        down_dates: list = list()

        response = {
            'service': service_name,
            'current_status': current_status,
            'current_down_time': 0,
            'next_up_time': 0,
            'next_down_time': 0,
        }

        if not service_name:
            return response

        # convert timezone to local timezone
        check_date_local = pytz.utc.localize(check_date).astimezone(pytz.timezone('US/Pacific'))
        current_app.logger.debug(f'check date local: {check_date_local}')

        check_date_aware: datetime = check_date_local.replace(hour=0, minute=0, second=0, microsecond=0)
        current_app.logger.debug(f'check date aware: {check_date_aware}')
        check_date_with_hours_aware: datetime = check_date_local.replace(second=0, microsecond=0)

        schedule = self.get_schedules(service_name)
        if schedule is not None:
            for i in schedule:
                uptime: datetime = check_date_aware
                downtime: datetime = check_date_aware + timedelta(1)
                schedule_date: date = check_date_aware.date()
                if 'up' in i:
                    uptime = croniter(i['up'], check_date_aware).get_next(datetime)
                    if uptime > check_date_local:
                        up_dates.append(uptime)
                    schedule_date = uptime.date()

                if 'down' in i:
                    downtime = croniter(i['down'], check_date_aware).get_next(datetime)
                    down_dates.append(downtime)
                    schedule_date = downtime.date()

                current_app.logger.debug(f'check date: {check_date_with_hours_aware}')
                current_app.logger.debug(f'uptime: {uptime}')
                current_app.logger.debug(f'downtime: {downtime}')

                if schedule_date == check_date_aware.date():
                    current_status = bool(check_date_with_hours_aware >= uptime)
                    if downtime > uptime:
                        current_status = bool(downtime > check_date_with_hours_aware)
                else:
                    if schedule_date < check_date_aware.date():
                        current_status = False

            response['current_status'] = current_status

            down_time = self.get_nearest_datetime(down_dates, check_date_local)
            up_time = self.get_nearest_datetime(up_dates, check_date_local)

            if current_status:
                response['next_down_time'] = down_time
            else:
                response['current_down_time'] = down_time
                response['next_up_time'] = up_time

        return response

    @staticmethod
    def get_schedules(service_name: str):
        """Search schedules from configuration by service name."""
        schedule_json: json = json.loads(current_app.config.get('SERVICE_SCHEDULE'))

        for service_schedule in schedule_json:
            # look up service
            if service_schedule['service_name'] == service_name:
                return service_schedule['schedules']

        return None

    @staticmethod
    def get_nearest_datetime(dates: list, check_date):
        """get a closest date from giving date in a date list."""
        closest_datetime: datetime = 0
        if dates and check_date:
            closest_date: datetime = min(dates, key=lambda x: abs(x - check_date))
            closest_datetime = closest_date.timestamp()

        return closest_datetime
