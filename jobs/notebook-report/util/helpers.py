"""Utility functions for email attachment processing."""

import fnmatch
import os
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase

import pytz
from dateutil.relativedelta import relativedelta


def get_utc_timezone_adjusted_date(target_date) -> str:
    """Get UTC timezone adjusted date."""
    target_datetime = datetime.combine(target_date, datetime.min.time())
    hours = target_datetime.astimezone(pytz.timezone("America/Vancouver")).utcoffset().total_seconds() / 60 / 60
    target_date = target_datetime.replace(tzinfo=timezone.utc) + relativedelta(hours=-hours)
    return target_date.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def get_first_last_month_dates_in_utc(override_current_date="") -> tuple[str, str]:
    """Get first and last month dates in UTC."""
    current_time = (
        datetime.strptime(override_current_date, "%Y-%m-%d")
        if override_current_date
        else datetime.now(pytz.timezone("America/Vancouver"))
    )
    last_month = current_time - relativedelta(months=1)
    from_date = last_month.replace(day=1)
    from_date = get_utc_timezone_adjusted_date(from_date)
    to_date = last_month.replace(day=1) + relativedelta(months=1)
    to_date = get_utc_timezone_adjusted_date(to_date)
    return from_date, to_date


def get_first_last_week_dates_in_utc(override_current_date="") -> tuple[str, str]:
    """Get first and last week dates in UTC."""
    current_time = (
        datetime.strptime(override_current_date, "%Y-%m-%d")
        if override_current_date
        else datetime.now(pytz.timezone("America/Vancouver"))
    )
    last_month = current_time - relativedelta(months=1)
    from_date = last_month.replace(day=1)
    from_date = get_utc_timezone_adjusted_date(from_date)
    to_date = last_month.replace(day=1) + relativedelta(months=1)
    to_date = get_utc_timezone_adjusted_date(to_date)
    return from_date, to_date


def create_temporary_directory():
    """Create temporary directory."""
    temp_dir = os.path.join(os.getcwd(), r"data/")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    return temp_dir


def find_files(directory, pattern):
    """Find files matched."""
    if not os.path.exists(directory):
        return
    for filename in os.listdir(directory):
        if fnmatch.fnmatch(filename.lower(), pattern):
            yield os.path.join(directory, filename)


def process_email_attachments(filenames, message):
    """Process email attachments."""
    for file in filenames:
        part = MIMEBase("application", "octet-stream")
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {file}",
        )
        file = os.path.join(os.getcwd(), r"data/") + file
        with open(file, "rb") as attachment:
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        message.attach(part)
