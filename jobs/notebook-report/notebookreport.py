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
from flask import Flask, current_app

from config import Config
from util.helpers import (
    ReportData,
    ReportFiles,
    convert_utc_date_to_inclusion_dates,
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


def build_subject(report: ReportData):
    """Build email subject."""
    date_str = datetime.strftime(datetime.now() - timedelta(days=1), "%Y-%m-%d")
    ext = f" on {Config.ENVIRONMENT}" if Config.ENVIRONMENT != "prod" else ""
    if report.error_message:
        return f"Notebook Report Error {report.file_processing} on {date_str}{ext}"
    match report.file_processing:
        case ReportFiles.WEEKLY_PAY:
            return f"Weekly PAY Stats till {date_str} {ext}"
        case ReportFiles.RECONCILIATION_SUMMARY:
            date_string, is_monthly = convert_utc_date_to_inclusion_dates(report.from_date, report.to_date)
            if is_monthly:
                return f"{report.partner_code} Monthly Reconciliation Stats from {date_string} {ext}"
            else:
                return f"{report.partner_code} Weekly Reconciliation Stats from {date_string} {ext}"


def build_recipients(report: ReportData):
    """Build email recipients."""
    if report.error_message:
        return Config.ERROR_EMAIL_RECIPIENTS
    match report.file_processing:
        case ReportFiles.WEEKLY_PAY:
            return Config.WEEKLY_PAY_RECIPIENTS
        case ReportFiles.RECONCILIATION_SUMMARY:
            return getattr(Config, f"{report.partner_code.upper()}_RECONCILIATION_RECIPIENTS", "")


def build_filenames(report: ReportData):
    """Get filenames."""
    condition = "weekly_pay_stats_till_" if report.file_processing == ReportFiles.WEEKLY_PAY else report.partner_code
    if condition:
        return [f for f in os.listdir(os.path.join(os.getcwd(), r"data/")) if f.startswith(condition)]
    return []


def build_and_send_email(report: ReportData):
    """Send email for results."""
    message = MIMEMultipart()
    if report.error_message:
        message.attach(MIMEText("ERROR!!! \n" + report.error_message, "plain"))
    else:
        message.attach(MIMEText("Please see the attachment(s).", "plain"))
    subject = build_subject(report)
    recipients = build_recipients(report)
    filenames = build_filenames(report)
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
    today = (
        datetime.strptime(Config.OVERRIDE_CURRENT_DATE, "%Y-%m-%d") if Config.OVERRIDE_CURRENT_DATE else date.today()
    )
    logging.info("Today's date: %s", today)

    logging.info(f"Weekly running report dates: {Config.WEEKLY_REPORT_DATES}")
    if today.isoweekday() in Config.WEEKLY_REPORT_DATES:
        from_date, to_date = get_first_last_week_dates_in_utc(Config.OVERRIDE_CURRENT_DATE)
        for partner_code in Config.WEEKLY_RECONCILIATION_PARTNERS.split(","):
            logging.info(
                "Processing weekly notebooks for partner: %s using dates: %s to %s ", partner_code, from_date, to_date
            )
            execute_notebook(ReportFiles.RECONCILIATION_SUMMARY, data_dir, from_date, to_date, partner_code)

    logging.info(f"Monthly running report dates: {Config.MONTHLY_REPORT_DATES}")
    if today.day in Config.MONTHLY_REPORT_DATES:
        from_date, to_date = get_first_last_month_dates_in_utc(Config.OVERRIDE_CURRENT_DATE)
        for partner_code in Config.MONTHLY_RECONCILIATION_PARTNERS.split(","):
            logging.info(
                "Processing monthly notebooks for partner: %s using dates: %s to %s", partner_code, from_date, to_date
            )
            execute_notebook(ReportFiles.RECONCILIATION_SUMMARY, data_dir, from_date, to_date, partner_code)


def execute_notebook(file: str, data_dir: str, from_date=None, to_date=None, partner_code=None):
    """Execute notebook and send emails."""
    try:
        pm.execute_notebook(
            file,
            data_dir + "temp.ipynb",
            parameters={"partner_code": partner_code, "from_date": from_date, "to_date": to_date},
        )
        build_and_send_email(ReportData(file, None, from_date, to_date, partner_code))
        os.remove(data_dir + "temp.ipynb")
    except Exception:  # noqa: B902
        logging.exception("Error: %s.", file)
        build_and_send_email(ReportData(file, traceback.format_exc()))


if __name__ == "__main__":
    start_time = datetime.now(tz=timezone.utc)
    temp_dir = create_temporary_directory()
    process_partner_notebooks(temp_dir)
    # Monday is 1 and Sunday is 7 - Run Pay report weekly.
    if date.today().isoweekday() in Config.WEEKLY_REPORT_DATES:
        execute_notebook(ReportFiles.WEEKLY_PAY, temp_dir)
    logging.info("Jupyter notebook report completed in: %s", datetime.now(tz=timezone.utc) - start_time)
    sys.exit()
