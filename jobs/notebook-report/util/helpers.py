"""Utility functions for email attachment processing."""

import fnmatch
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from enum import Enum

import pytz
import requests
from dateutil.relativedelta import relativedelta

from config import Config


@dataclass
class ReportData:
    """Representation of a report."""

    file_processing: str = ""
    error_message: str = None
    from_date: str = None
    to_date: str = None
    partner_code: str = None


class ReportFiles(Enum):
    """Report names."""

    WEEKLY_PAY = "weekly/pay.ipynb"
    RECONCILIATION_SUMMARY = "reports/reconciliation_summary.ipynb"


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
    from_date = current_time - timedelta(days=7)
    from_date = get_utc_timezone_adjusted_date(from_date)
    to_date = current_time
    to_date = get_utc_timezone_adjusted_date(to_date)
    return from_date, to_date


def convert_utc_date_to_inclusion_dates(from_date: str, to_date: str, output_format="default"):
    """Convert UTC date to display date for ranges that are in pacific time, detect monthly."""
    is_monthly = datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S") + relativedelta(months=1) <= datetime.strptime(
        to_date, "%Y-%m-%d %H:%M:%S"
    )
    # Take off a day because we want to include the last day in the range, UTC is a day ahead
    to_date_str = datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S") - relativedelta(days=1)
    date_string = from_date.split(" ")[0] + " to " + to_date_str.strftime("%Y-%m-%d")

    def format_date_full(date_obj):
        """Format the date as "Month DaySuffix, Year."""
        day = date_obj.day
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return date_obj.strftime(f"%B {day}{suffix}, %Y")

    if output_format == "full":
        date_string = (
            f"{format_date_full(datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S"))} to {format_date_full(to_date_str)}"
        )

    return date_string, is_monthly


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


def get_auth_token():
    """Get authentication token from Keycloak."""
    client = Config.NOTEBOOK_SERVICE_ACCOUNT_ID
    secret = Config.NOTEBOOK_SERVICE_ACCOUNT_SECRET
    kc_url = Config.JWT_OIDC_ISSUER + "/protocol/openid-connect/token"

    response = requests.post(
        url=kc_url,
        data="grant_type=client_credentials",
        headers={"content-type": "application/x-www-form-urlencoded"},
        auth=(client, secret),
    )

    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception("Failed to get authentication token")  # pylint: disable=broad-exception-raised
