
from datetime import datetime
import holidays
import pytz

from flask import current_app

def is_holiday():
    current_date_pacific = datetime.now(tz=pytz.utc).astimezone(pytz.timezone('US/Pacific')).strftime('%Y-%m-%d')
    if holiday := holidays.CA(state='BC', observed=False).get(current_date_pacific):
        current_app.logger.info(f'Today is a stat holiday {holiday} on {current_date_pacific}')
        return True
    return False
