"""The Notebook Report - This module is the API for the Pay Notebook Report."""

import base64
import logging
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

import papermill as pm
import requests
from flask import Flask, current_app

from config import Config
from util.helpers import (
    ReportData,
    ReportFiles,
    convert_utc_date_to_inclusion_dates,
    create_temporary_directory,
    get_auth_token,
    get_first_last_month_dates_in_utc,
    get_first_last_week_dates_in_utc,
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
        case ReportFiles.WEEKLY_PAY.value:
            return f"Weekly PAY Stats till {date_str} {ext}"
        case ReportFiles.RECONCILIATION_SUMMARY.value:
            date_string, _ = convert_utc_date_to_inclusion_dates(report.from_date, report.to_date)
            return f"{report.partner_code} Reconciliation Stats from {date_string} {ext}"


def build_recipients(report: ReportData):
    """Build email recipients."""
    if report.error_message:
        return Config.ERROR_EMAIL_RECIPIENTS
    match report.file_processing:
        case ReportFiles.WEEKLY_PAY.value:
            return Config.WEEKLY_PAY_RECIPIENTS
        case ReportFiles.RECONCILIATION_SUMMARY.value:
            return getattr(Config, f"{report.partner_code.upper()}_RECONCILIATION_RECIPIENTS", "")


def build_filenames(report: ReportData):
    """Get filenames."""
    condition = "weekly_pay_stats_till_" if report.file_processing == ReportFiles.WEEKLY_PAY else report.partner_code
    if condition:
        return [f for f in os.listdir(os.path.join(os.getcwd(), r"data/")) if f.startswith(condition)]
    return []


def build_and_send_email(report: ReportData):
    """Send email for results."""

    token = get_auth_token()
    subject = build_subject(report)
    recipients = build_recipients(report)
    filenames = build_filenames(report)
    
    email = {
        'recipients': recipients,
        'content': {
            'subject': subject,
            'body': 'Please see the attachment(s).',
            'attachments': []
        }
    }
    
    if report.error_message:
        email['content']['body'] = 'ERROR!!! \n' + report.error_message
    else:
        try:
            for filename in filenames:
                file_path = os.path.join(os.getcwd(), "data", filename)
                with open(file_path, "rb") as f:
                    file_encoded = base64.b64encode(f.read())
                    email['content']['attachments'].append({
                        'fileName': filename,
                        'fileBytes': file_encoded.decode(),
                        'fileUrl': '',
                        'attachOrder': len(email['content']['attachments']) + 1
                    })
        except Exception:  # noqa: B902
            logging.error('Error processing attachments')
            email = {
                'recipients': Config.ERROR_EMAIL_RECIPIENTS,
                'content': {
                    'subject': 'Error Notification ' + subject,
                    'body': 'Failed to generate report: ' + traceback.format_exc(),
                    'attachments': []
                }
            }
    
    

        
    send_email(email, token)


def send_email(email: dict, token):
    """Send the email."""
    if Config.DISABLE_EMAIL is True:
        return
        
    response = requests.request("POST",
        Config.NOTIFY_API_URL,
        json=email,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    if response.status_code == 200:
        logging.info('The email was sent successfully')
    else:    
        logging.error(f'response:{response}')
        raise Exception('Unsuccessful response when sending email.')


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
            execute_notebook(ReportFiles.RECONCILIATION_SUMMARY.value, data_dir, from_date, to_date, partner_code)

    logging.info(f"Monthly running report dates: {Config.MONTHLY_REPORT_DATES}")
    if today.day in Config.MONTHLY_REPORT_DATES:
        from_date, to_date = get_first_last_month_dates_in_utc(Config.OVERRIDE_CURRENT_DATE)
        for partner_code in Config.MONTHLY_RECONCILIATION_PARTNERS.split(","):
            logging.info(
                "Processing monthly notebooks for partner: %s using dates: %s to %s", partner_code, from_date, to_date
            )
            execute_notebook(ReportFiles.RECONCILIATION_SUMMARY.value, data_dir, from_date, to_date, partner_code)


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
        execute_notebook(ReportFiles.WEEKLY_PAY.value, temp_dir)
    logging.info("Jupyter notebook report completed in: %s", datetime.now(tz=timezone.utc) - start_time)
    sys.exit()
