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

"""CORS pre-flight decorator.

A simple decorator to add the options method to a Request Class.
"""
import ast
import calendar
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Dict
from urllib.parse import parse_qsl, urlparse

import pytz
from dpath import get as dpath_get
from flask import current_app
from holidays.constants import GOVERNMENT, OPTIONAL, PUBLIC
from holidays.countries import Canada

from .constants import DT_SHORT_FORMAT
from .converter import Converter
from .enums import Code, CorpType, Product, StatementFrequency


def cors_preflight(methods: str = "GET"):
    """Render an option method on the class."""

    def wrapper(f):
        def options(self, *args, **kwargs):  # pylint: disable=unused-argument
            return (
                {"Allow": methods},
                200,
                {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": methods,
                    "Access-Control-Allow-Headers": "Authorization, Content-Type, registries-trace-id, Account-Id",
                },
            )

        setattr(f, "options", options)
        return f

    return wrapper


def normalize_url(url: str) -> str:
    """Normalize the URL by removing 'www.' if present and strip trailing slash."""
    parsed = urlparse(url)
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{netloc}{path}"


def is_valid_redirect_url(url: str) -> bool:
    """Validate if the url is valid based on the VALID Redirect Url."""
    disable_redirect_validation: bool = current_app.config.get("DISABLE_VALID_REDIRECT_URLS")
    if disable_redirect_validation:
        return True
    valid_urls: list = current_app.config.get("VALID_REDIRECT_URLS")
    is_valid = False
    url = normalize_url(url)
    for valid_url in valid_urls:
        valid_url = normalize_url(valid_url)
        is_valid = url.startswith(normalize_url(valid_url[:-1])) if valid_url.endswith("*") else valid_url == url
        if is_valid:
            break
    return is_valid


def convert_to_bool(value: str) -> bool:
    """Convert string to boolean."""
    return value.lower() == "true"


def get_str_by_path(payload: Dict, path: str) -> str:
    """Return the string value from the dict for the path using dpath library."""
    if payload is None:
        return None

    try:
        raw = dpath_get(payload, path)
        return str(raw) if raw is not None else raw
    except (IndexError, KeyError, TypeError):
        return None


def get_week_start_and_end_date(target_date: datetime = datetime.now(tz=timezone.utc), index: int = 0):
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
    start_date = datetime.now(tz=timezone.utc).replace(day=1, year=year, month=month)
    end_date = start_date.replace(day=calendar.monthrange(year=year, month=month)[1])
    return start_date, end_date


def get_previous_month_and_year(target_date=datetime.now(tz=timezone.utc)):
    """Return last month and year."""
    last_month = target_date.replace(day=1) - timedelta(days=1)
    return last_month.month, last_month.year


def get_previous_day(val: datetime):
    """Return previous day."""
    # index: 0 (current week), 1 (last week) and so on
    return val - timedelta(days=1)


def get_first_and_last_of_frequency(date: datetime, frequency: str):
    """Return first day of the specified frequency."""
    if frequency == StatementFrequency.MONTHLY.value:
        return get_first_and_last_dates_of_month(date.month, date.year)
    if frequency == StatementFrequency.WEEKLY.value:
        return get_week_start_and_end_date(date)
    return None, None


def parse_url_params(url_params: str) -> Dict:
    """Parse URL params and return dict of parsed url params."""
    parsed_url: dict = {}
    if url_params is not None:
        if url_params.startswith("?"):
            url_params = url_params[1:]
        parsed_url = dict(parse_qsl(url_params))

    return parsed_url


def current_local_time(timezone_override=None) -> datetime:
    """Return current local time."""
    today = datetime.now(tz=timezone.utc)
    return get_local_time(today, timezone_override)


def get_local_time(date_val: datetime, timezone_override=None):
    """Return local time value."""
    tz_name = timezone_override or current_app.config["LEGISLATIVE_TIMEZONE"]
    tz_local = pytz.timezone(tz_name)
    date_val = date_val.astimezone(tz_local)
    return date_val


def get_local_formatted_date_time(date_val: datetime, dt_format: str = "%Y-%m-%d %H:%M:%S"):
    """Return formatted local time."""
    return get_local_time(date_val).strftime(dt_format)


def get_local_formatted_date(date_val: datetime, dt_format: str = "%Y-%m-%d"):
    """Return formatted local time."""
    return get_local_time(date_val).strftime(dt_format)


def generate_transaction_number(txn_number: str) -> str:
    """Return transaction number for invoices."""
    prefix = current_app.config.get("CFS_INVOICE_PREFIX")
    return f"{prefix}{txn_number:0>8}"


def get_fiscal_year(date_val: datetime = datetime.now(tz=timezone.utc)) -> int:
    """Return fiscal year for the date."""
    fiscal_year: int = date_val.year
    if date_val.month > 3:  # Up to March 31, use the current year.
        fiscal_year = fiscal_year + 1
    return fiscal_year


def generate_receipt_number(payment_id: str) -> str:
    """Return receipt number for payments."""
    prefix = current_app.config.get("CFS_RECEIPT_PREFIX")
    return f"{prefix}{payment_id:0>8}"


def mask(val: str, preserve_length: int = 0) -> str:
    """Mask the val.only unmask the length specified."""
    if not val:
        return val
    replace_char = "X"
    if preserve_length is None or preserve_length == 0:  # mask fully
        return replace_char * len(val)
    return val[-preserve_length:].rjust(len(val), replace_char)


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
    # Even though not officially a BC STAT - Union recognizes Easter Monday and Boxing Day.
    # https://www2.gov.bc.ca/gov/content/careers-myhr/all-employees/leave-time-off/vacations-holidays/statutory-holidays
    holiday = Canada(
        subdiv="BC",
        observed=True,
        categories=(GOVERNMENT, OPTIONAL, PUBLIC),
        years=val.year,
    )
    holiday._add_easter_monday("Easter Monday")  # pylint: disable=protected-access
    if holiday.get(val.strftime("%Y-%m-%d")):
        return True
    if val.weekday() >= 5:
        return True
    return False


def get_next_day(val: datetime):
    """Return next day."""
    # index: 0 (current week), 1 (last week) and so on
    return val + timedelta(days=1)


def get_outstanding_txns_from_date() -> datetime:
    """Return the date value which can be used as start date to calculate outstanding PAD transactions."""
    days_interval: int = current_app.config.get("OUTSTANDING_TRANSACTION_DAYS")
    from_date = datetime.now(tz=timezone.utc)
    # Find the business day before days_interval time.
    counter: int = 0
    while counter < days_interval:
        from_date = from_date - timedelta(days=1)
        if not is_holiday(from_date):
            counter += 1
    return from_date


def string_to_date(date_val: str, dt_format: str = DT_SHORT_FORMAT):
    """Return formatted local time."""
    if date_val is None:
        return None

    return datetime.strptime(date_val, dt_format).date()


def string_to_decimal(val: str):
    """Return decimal from string."""
    if val is None:
        return None

    return Decimal(val)


def string_to_int(val: str):
    """Return int from string."""
    if val is None:
        return None

    return int(val)


def string_to_bool(val: str):
    """Return bool from string."""
    if val is None:
        return None
    if val.lower() not in ("true", "false"):
        raise ValueError(f"Invalid string value for bool: {val}")

    return ast.literal_eval(val.capitalize())


def get_quantized(amount: float) -> Decimal:
    """Return rounded decimal. (Default = ROUND_HALF_EVEN)."""
    return Decimal(amount).quantize(Decimal("1.00"))


def cents_to_decimal(amount: int):
    """Return dollar amount from cents."""
    if amount is None:
        return None

    return amount / 100


def get_topic_for_corp_type(corp_type: str):
    """Return a topic to direct the queue message to."""
    # Will fix this promptly and move this away so it doesn't cause circular dependencies.
    from ..services.code import Code as CodeService  # pylint: disable=import-outside-toplevel

    if corp_type == CorpType.NRO.value:
        return current_app.config.get("NAMEX_PAY_TOPIC")
    product_code = CodeService.find_code_value_by_type_and_code(Code.CORP_TYPE.value, corp_type).get("product")
    if product_code in [Product.BUSINESS.value, Product.BUSINESS_SEARCH.value]:
        return current_app.config.get("BUSINESS_PAY_TOPIC")
    if product_code == Product.STRR.value:
        return current_app.config.get("STRR_PAY_TOPIC")
    return None


def unstructure_schema_items(schema, items):
    """Return unstructured results by schema."""
    results = [schema.from_row(item) for item in items]
    converter = Converter()

    return converter.unstructure(results)


def get_midnight_vancouver_time_from_utc():
    """Get the midnight vancouver time from UTC date adjusted for daylight savings."""
    target_date = datetime.now(tz=timezone.utc).date()
    target_datetime = datetime.combine(target_date, datetime.min.time())
    # Correct for daylight savings.
    hours = target_datetime.astimezone(pytz.timezone("America/Vancouver")).utcoffset().total_seconds() / 60 / 60
    target_date = target_datetime.replace(tzinfo=timezone.utc) + relativedelta(hours=-hours)
    return target_date
