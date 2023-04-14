"""Date utility to determine if CGI feeder should execute or not."""
from datetime import datetime
import holidays
import pytz

from flask import current_app


def is_holiday_or_weekend():
    """Determine if day is a holiday or weekend, CGI feeders only work on weekdays."""
    current_date_pacific = datetime.now(tz=pytz.utc).astimezone(pytz.timezone('US/Pacific'))
    if holiday := holidays.CA(state='BC', observed=False).get(current_date_pacific.strftime('%Y-%m-%d')):
        current_app.logger.info(f'Today is a stat holiday {holiday} on {current_date_pacific}')
        return True
    if current_date_pacific.weekday() >= 5:
        weekend_day = 'saturday' if current_date_pacific.weekday() == 5 else 'sunday'
        current_app.logger.info(f'Today is a {weekend_day} on {current_date_pacific}')
        return True
    return False
