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

"""CORS pre-flight decorator.

A simple decorator to add the options method to a Request Class.
"""
import calendar
from datetime import datetime, timedelta
from typing import Dict
from decimal import Decimal
from urllib.parse import parse_qsl

import pytz
from dateutil.parser import parse
from dpath import util as dpath_util
from flask import current_app

from .constants import DT_SHORT_FORMAT
from .enums import CorpType


def cors_preflight(methods: str = 'GET'):
    """Render an option method on the class."""

    def wrapper(f):
        def options(self, *args, **kwargs):  # pylint: disable=unused-argument
            return {'Allow': methods}, 200, \
                   {'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': methods,
                    'Access-Control-Allow-Headers': 'Authorization, Content-Type, registries-trace-id, Account-Id'}

        setattr(f, 'options', options)
        return f

    return wrapper


def is_valid_redirect_url(url: str) -> bool:
    """Validate if the url is valid based on the VALID Redirect Url."""
    valid_urls: list = current_app.config.get('VALID_REDIRECT_URLS')
    is_valid = False
    for valid_url in valid_urls:
        is_valid = url.startswith(valid_url[:-1]) if valid_url.endswith('*') else valid_url == url
        if is_valid:
            break
    return is_valid


def convert_to_bool(value: str) -> bool:
    """Convert string to boolean."""
    return value.lower() == 'true'


def get_str_by_path(payload: Dict, path: str) -> str:
    """Return the string value from the dict for the path using dpath library."""
    if payload is None:
        return None

    try:
        raw = dpath_util.get(payload, path)
        return str(raw) if raw is not None else raw
    except (IndexError, KeyError, TypeError):
        return None


def get_week_start_and_end_date(target_date: datetime = datetime.now(), index: int = 0):
    """Return first and last dates (sunday and saturday) for the index."""
    # index: 0 (current week), 1 (last week) and so on
    date = target_date - timedelta(days=index * 6)
    rewind_days = date.weekday() + 1
    # Fix for sunday.
    rewind_days = 0 if rewind_days == 7 else rewind_days
    start = date - timedelta(days=rewind_days)
    end = start + timedelta(days=6)
    return start, end


def get_first_and_last_dates_of_month(month: int, year: int):
    """Return first and last dates for a given month and year."""
    start_date = datetime.now().replace(day=1, year=year, month=month)
    end_date = start_date.replace(day=calendar.monthrange(year=year, month=month)[1])
    return start_date, end_date


def get_previous_month_and_year():
    """Return last month and year."""
    last_month = datetime.now().replace(day=1) - timedelta(days=1)
    return last_month.month, last_month.year


def get_previous_day(val: datetime):
    """Return previous day."""
    # index: 0 (current week), 1 (last week) and so on
    return val - timedelta(days=1)


def parse_url_params(url_params: str) -> Dict:
    """Parse URL params and return dict of parsed url params."""
    parsed_url: dict = {}
    if url_params is not None:
        if url_params.startswith('?'):
            url_params = url_params[1:]
        parsed_url = dict(parse_qsl(url_params))

    return parsed_url


def current_local_time() -> datetime:
    """Return current local time."""
    today = datetime.now()
    return get_local_time(today)


def get_local_time(date_val: datetime):
    """Return local time value."""
    tz_name = current_app.config['LEGISLATIVE_TIMEZONE']
    tz_local = pytz.timezone(tz_name)
    date_val = date_val.astimezone(tz_local)
    return date_val


def get_local_formatted_date_time(date_val: datetime, dt_format: str = '%Y-%m-%d %H:%M:%S'):
    """Return formatted local time."""
    return get_local_time(date_val).strftime(dt_format)


def get_local_formatted_date(date_val: datetime, dt_format: str = '%Y-%m-%d'):
    """Return formatted local time."""
    return get_local_time(date_val).strftime(dt_format)


def generate_transaction_number(txn_number: str) -> str:
    """Return transaction number for invoices."""
    prefix = current_app.config.get('CFS_INVOICE_PREFIX')
    return f'{prefix}{txn_number:0>8}'


def get_fiscal_year(date_val: datetime = datetime.now()) -> int:
    """Return fiscal year for the date."""
    fiscal_year: int = date_val.year
    if date_val.month > 3:  # Up to March 31, use the current year.
        fiscal_year = fiscal_year + 1
    return fiscal_year


def generate_receipt_number(payment_id: str) -> str:
    """Return receipt number for payments."""
    prefix = current_app.config.get('CFS_RECEIPT_PREFIX')
    return f'{prefix}{payment_id:0>8}'


def mask(val: str, preserve_length: int = 0) -> str:
    """Mask the val.only unmask the length specified."""
    if not val:
        return val
    replace_char = 'X'
    if preserve_length is None or preserve_length == 0:  # mask fully
        return replace_char * len(val)
    return val[-preserve_length:].rjust(len(val), replace_char)


def get_pay_subject_name(corp_type: str, subject_format: str = None):
    """Return payment subject name."""
    # TODO Refactor later
    subject_format = subject_format or current_app.config.get('NATS_PAYMENT_SUBJECT')

    if corp_type == CorpType.NRO.value:
        pay_subject = 'name-request'
    elif corp_type == CorpType.PPR.value:
        pay_subject = 'ppr'
    elif corp_type == CorpType.VS.value:
        pay_subject = 'vs'
    else:
        pay_subject = 'filing'
    return subject_format.format(product=pay_subject)


def get_nearest_business_day(date_val: datetime, include_today: bool = True) -> datetime:
    """Return nearest business day to the date.

    include_today= true ; inclusive of today.If today is business , just returns it
    include_today= false; exclude today. Returns the business day from date+1
    """
    if not include_today:
        date_val = get_next_day(date_val)
    if not is_holiday(date_val):
        return date_val
    # just a recursive call to get the next business day.
    return get_nearest_business_day(get_next_day(date_val))


def is_holiday(val: datetime) -> bool:
    """Return receipt number for payments.

    saturday or sunday check
    check the BC holidays
    """
    week_number: int = val.weekday()
    if week_number > 4:  # 5- saturday 6 sunday
        return True
    holidays_list = current_app.config.get('HOLIDAYS_LIST')
    holidays_dates_list = [parse(date).date() for date in holidays_list.split(',')]
    if val.date() in holidays_dates_list:
        return True
    return False


def get_next_day(val: datetime):
    """Return next day."""
    # index: 0 (current week), 1 (last week) and so on
    return val + timedelta(days=1)


def get_outstanding_txns_from_date() -> datetime:
    """Return the date value which can be used as start date to calculate outstanding PAD transactions."""
    days_interval: int = current_app.config.get('OUTSTANDING_TRANSACTION_DAYS')
    from_date = datetime.now()
    # Find the business day before days_interval time.
    counter: int = 0
    while counter < days_interval:
        from_date = from_date - timedelta(days=1)
        if not is_holiday(from_date):
            counter += 1
    return from_date


def string_to_date(date_val: str, dt_format: str = DT_SHORT_FORMAT):
    """Return formatted local time."""
    return datetime.strptime(date_val, dt_format).date()


def get_quantized(amount: float) -> Decimal:
    """Return rounded decimal. (Default = ROUND_HALF_EVEN)."""
    return Decimal(amount).quantize(Decimal('1.00'))
