"""The Notebook Report - This module is the API for the Pay Notebook Report."""

import logging
import os
import smtplib
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import papermill as pm
import pytz
from dateutil.relativedelta import relativedelta
from flask import Flask, current_app

from config import Config
from util.helpers import (
    create_temporary_directory,
    get_first_last_month_dates_in_utc,
    get_first_last_week_dates_in_utc,
    process_email_attachments,
)
from util.logging import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), "logging.conf"))  # important to do this first

# This script helps with the automated processing of Jupyter Notebooks via
# papermill (https://github.com/nteract/papermill/)


def create_app(config=Config):
    """Create app."""
    app = Flask(__name__)
    app.config.from_object(config)
    app.app_context().push()
    current_app.logger.debug("created the Flask App and pushed the App Context")
    return app


def build_subject(file_processing, partner_code):
    """Build email subject."""
    date_str = datetime.strftime(datetime.now() - timedelta(1), "%Y-%m-%d")
    ext = f" on {Config.ENVIRONMENT}" if Config.ENVIRONMENT != "prod" else ""
    match file_processing:
        case "pay":
            return "Weekly PAY Stats till " + date_str + ext
        case "reconciliation_summary":
            override_current_date = Config.OVERRIDE_CURRENT_DATE
            current_time = (
                datetime.strptime(override_current_date, "%Y-%m-%d")
                if override_current_date
                else datetime.now(pytz.timezone("America/Vancouver"))
            )
            last_month = current_time - relativedelta(months=1)
            last_month = last_month.replace(day=1)
            year_month = datetime.strftime(last_month, "%Y-%m")
            # TODO figure out for weekly or monthly, we should calculate the dates and pass it in.
            return f"{partner_code} Monthly Reconciliation Stats for {year_month}{ext}"


def build_recipients(email_type, file_processing, partner_code):
    """Build email recipients."""
    if email_type == "ERROR":
        return Config.ERROR_EMAIL_RECIPIENTS
    match file_processing:
        case "pay":
            return Config.WEEKLY_PAY_RECIPIENTS
        case "reconciliation_summary":
            return getattr(Config, f"{partner_code.upper()}_RECONCILIATION_RECIPIENTS", "")


def build_filenames(file_processing, partner_code):
    """Get filenames."""
    condition = "weekly_pay_stats_till_" if file_processing == "pay" else partner_code
    return [f for f in os.listdir(os.path.join(os.getcwd(), r"data/")) if f.startswith(condition)]


def build_and_send_email(file_processing, email_type, error_message, partner_code=None):
    """Send email for results."""
    message = MIMEMultipart()
    if email_type == "ERROR":
        message.attach(MIMEText("ERROR!!! \n" + error_message, "plain"))
    else:
        message.attach(MIMEText("Please see the attachment(s).", "plain"))
    subject = build_subject(file_processing, partner_code)
    recipients = build_recipients(email_type, file_processing, partner_code)
    filenames = build_filenames(file_processing, partner_code)
    process_email_attachments(filenames, message)
    send_email(message, subject, recipients)


def send_email(message, subject, recipients):
    """Send email."""
    if Config.DISABLE_EMAIL is True:
        return
    message["Subject"] = subject
    server = smtplib.SMTP(Config.EMAIL_SMTP)
    email_list = recipients.strip("][").split(", ")
    logging.info("Email recipients list is: %s", email_list)
    server.sendmail(Config.SENDER_EMAIL, email_list, message.as_string())
    logging.info("Email with subject '%s' has been sent successfully!", subject)
    server.quit()


def process_partner_notebooks(data_dir: str):
    """Process Partner Notebook."""
    today = date.today().day
    logging.info("Today's date: %s", today)

    logging.info(f"Weekly running report dates: {Config.WEEKLY_REPORT_DATES}")
    if date.today().isoweekday() in Config.WEEKLY_REPORT_DATES:
        from_date, to_date = get_first_last_week_dates_in_utc(Config.OVERRIDE_CURRENT_DATE)
        for partner_code in Config.WEEKLY_RECONCILIATION_PARTNERS:
            logging.info(
                "Processing weekly notebooks for partner: %s using dates: %s %s ", partner_code, from_date, to_date
            )
            execute_notebook("reports/reconciliation_summary.ipynb", data_dir, from_date, to_date, partner_code)

    logging.info(f"Monthly running report dates: {Config.MONTHLY_REPORT_DATES}")
    if today in Config.MONTHLY_REPORT_DATES:
        from_date, to_date = get_first_last_month_dates_in_utc(Config.OVERRIDE_CURRENT_DATE)
        for partner_code in Config.MONTHLY_RECONCILIATION_PARTNERS:
            logging.info(
                "Processing monthly notebooks for partner: %s using dates: %s %s", partner_code, from_date, to_date
            )
            execute_notebook("reports/reconciliation_summary.ipynb", data_dir, from_date, to_date, partner_code)


def execute_notebook(file: str, data_dir: str, from_date=None, to_date=None, partner_code=None):
    """Execute notebook and send emails."""
    try:
        pm.execute_notebook(
            file,
            data_dir + "temp.ipynb",
            parameters={"partner_code": partner_code, "from_date": from_date, "to_date": to_date},
        )
        build_and_send_email(file, "", "", partner_code)
        os.remove(data_dir + "temp.ipynb")
    except Exception:  # noqa: B902
        logging.exception("Error: %s.", file)
        build_and_send_email(file, "ERROR", traceback.format_exc())


if __name__ == "__main__":
    start_time = datetime.now(tz=timezone.utc)
    temp_dir = create_temporary_directory()
    process_partner_notebooks(temp_dir)

    # Monday is 1 and Sunday is 7 - Run Pay report weekly.
    if date.today().isoweekday() in Config.WEEKLY_REPORT_DATES:
        execute_notebook("weekly/pay.ipynb", temp_dir)
    end_time = datetime.now(tz=timezone.utc)
    logging.info("Jupyter notebook report completed in: %s", end_time - start_time)
    sys.exit()
