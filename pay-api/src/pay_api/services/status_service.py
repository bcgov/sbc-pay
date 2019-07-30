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

    def schedule_status(self, service_name: str, check_date: datetime = datetime.today()):
        """Check service scheduled status ."""
        current_status: str = 'None'
        next_schedule_date: datetime = None

        response = {
            'service': service_name,
            'current_status': current_status,
            'next_schedule_date': next_schedule_date,
            'next_schedule_time': 0,
        }

        if not service_name:
            return response
        local_timezone = pytz.timezone('US/Pacific')
        check_date_aware: datetime = local_timezone.localize(
            check_date.replace(hour=0, minute=0, second=0, microsecond=0)
        )
        check_date_with_hours_aware: datetime = local_timezone.localize(check_date.replace(second=0, microsecond=0))

        schedule = self.get_schedules(service_name)
        if schedule is not None:
            for i in schedule:
                uptime: datetime = check_date_aware
                downtime: datetime = check_date_aware + timedelta(1)
                schedule_date: date = check_date_aware.date()
                if 'up' in i:
                    uptime = croniter(i['up'], check_date_aware).get_next(datetime)
                    schedule_date = uptime.date()
                if 'down' in i:
                    downtime = croniter(i['down'], check_date_aware).get_next(datetime)
                    schedule_date = downtime.date()
                    if next_schedule_date is None or next_schedule_date >= downtime:
                        next_schedule_date = downtime

                if schedule_date == check_date_aware.date():
                    current_status = bool(downtime > check_date_with_hours_aware >= uptime)
                else:
                    current_status = bool(schedule_date > check_date_aware.date())

            response['current_status'] = current_status
            if next_schedule_date:
                response['next_schedule_date'] = next_schedule_date
                response['next_schedule_time'] = next_schedule_date.timestamp()

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
