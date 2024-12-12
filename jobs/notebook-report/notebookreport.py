"""The Notebook Report - This module is the API for the Pay Notebook Report."""

import ast
import fnmatch
import logging
import os
import smtplib
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import papermill as pm
from flask import Flask, current_app

from config import Config
from util.logging import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), "logging.conf"))  # important to do this first

# Notebook Scheduler
# ---------------------------------------
# This script helps with the automated processing of Jupyter Notebooks via
# papermill (https://github.com/nteract/papermill/)


def create_app(config=Config):
    """Create app."""
    app = Flask(__name__)
    app.config.from_object(config)
    app.app_context().push()
    current_app.logger.debug("created the Flask App and pushed the App Context")

    return app


def findfiles(directory, pattern):
    """Find files matched."""
    for filename in os.listdir(directory):
        if fnmatch.fnmatch(filename.lower(), pattern):
            yield os.path.join(directory, filename)


def send_email(file_processing, emailtype, errormessage, partner_code=None):
    """Send email for results."""
    message = MIMEMultipart()
    date_str = datetime.strftime(datetime.now() - timedelta(1), "%Y-%m-%d")
    ext = ""
    filenames = []
    subject = ""
    recipients = ""
    if not Config.ENVIRONMENT == "prod":
        ext = " on " + Config.ENVIRONMENT

    if emailtype == "ERROR":
        subject = "Notebook Report Error '" + file_processing + "' on " + date_str + ext
        recipients = Config.ERROR_EMAIL_RECIPIENTS
        message.attach(MIMEText("ERROR!!! \n" + errormessage, "plain"))
    else:
        if "reconciliation_details" in file_processing:
            subject = "Daily Reconciliation Stats " + date_str + ext
            filenames = [f"{partner_code}_daily_reconciliation_" + date_str + ".csv"]
            recipients = get_partner_recipients(file_processing, partner_code)
        elif "pay" in file_processing:
            subject = "Weekly PAY Stats till " + date_str + ext
            filenames = ["weekly_pay_stats_till_" + date_str + ".csv"]
            recipients = Config.WEEKLY_PAY_RECIPIENTS
        elif "reconciliation_summary" in file_processing:
            year_month = datetime.strftime(datetime.now() - timedelta(1), "%Y-%m")
            subject = "Monthly Reconciliation Stats " + year_month + ext
            if partner_code in Config.PARTNER_CODES_DISBURSEMENT.split(","):
                filenames.append(f"{partner_code}_monthly_reconciliation_disbursed_" + year_month + ".csv")
            filenames = [
                f"{partner_code}_monthly_reconciliation_summary_" + year_month + ".csv",
                f"{partner_code}_revenue_letter.pdf",
            ]
            recipients = get_partner_recipients(file_processing, partner_code)

    # Add body to email
    message.attach(MIMEText("Please see the attachment(s).", "plain"))
    process_email_attachments(filenames, message)

    message["Subject"] = subject
    server = smtplib.SMTP(Config.EMAIL_SMTP)
    email_list = recipients.strip("][").split(", ")
    logging.info("Email recipients list is: %s", email_list)
    server.sendmail(Config.SENDER_EMAIL, email_list, message.as_string())
    logging.info("Email with subject '%s' has been sent successfully!", subject)
    server.quit()


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


def process_partner_notebooks(notebookdirectory: str, data_dir: str, partner_code: str):
    """Process Partner Notebook."""
    logging.info("Start processing partner notebooks directory: %s", notebookdirectory)

    try:
        monthly_report_dates = ast.literal_eval(Config.MONTHLY_REPORT_DATES)
    except Exception:  # noqa: B902
        logging.exception("Error parsing monthly report dates for: %s", notebookdirectory)
        send_email(notebookdirectory, "ERROR", traceback.format_exc())
        return

    today = date.today().day
    logging.info("Today's date: %s", today)

    if notebookdirectory == "daily":
        logging.info("Processing daily notebooks for partner: %s", partner_code)
        execute_notebook(notebookdirectory, data_dir, partner_code)

    logging.info(f"Monthly report dates: {monthly_report_dates}")
    if notebookdirectory == "monthly" and today in monthly_report_dates:
        logging.info("Processing monthly notebooks for partner: %s", partner_code)
        execute_notebook(notebookdirectory, data_dir, partner_code, is_monthly=True)


def process_notebooks(notebookdirectory: str, data_dir: str):
    """Process Notebook."""
    logging.info("Start processing directory: %s", notebookdirectory)

    try:
        weekly_report_dates = ast.literal_eval(Config.WEEKLY_REPORT_DATES)
    except Exception:  # noqa: B902
        logging.exception("Error: %s.", notebookdirectory)
        send_email(notebookdirectory, "ERROR", traceback.format_exc())

    # Monday is 1 and Sunday is 7
    if notebookdirectory == "weekly" and date.today().isoweekday() in weekly_report_dates:
        execute_notebook(notebookdirectory, data_dir)


def execute_notebook(notebookdirectory: str, data_dir: str, partner_code: str = None, is_monthly: bool = False):
    """Execute notebook and send emails."""
    parameters = {"partner_code": partner_code} if partner_code else None
    if is_monthly:
        pattern = "reconciliation_summary.ipynb"
    else:
        pattern = f"{partner_code.lower()}_*.ipynb" if partner_code else "*.ipynb"

    for file in findfiles(notebookdirectory, pattern):
        try:
            pm.execute_notebook(file, data_dir + "temp.ipynb", parameters=parameters)
            # send email to receivers and remove files/directories which we don't want to keep
            send_email(file, "", "", partner_code)
            os.remove(data_dir + "temp.ipynb")
        except Exception:  # noqa: B902
            logging.exception("Error: %s.", file)
            send_email(file, "ERROR", traceback.format_exc())


def get_partner_recipients(file_processing: str, partner_code: str) -> str:
    """Get email recipients for a partner."""
    if "reconciliation_details" in file_processing:
        return getattr(Config, f"{partner_code.upper()}_DAILY_RECONCILIATION_RECIPIENTS", "")

    if "reconciliation_summary" in file_processing:
        return getattr(Config, f"{partner_code.upper()}_MONTHLY_RECONCILIATION_RECIPIENTS", "")

    return None


if __name__ == "__main__":
    start_time = datetime.now(tz=timezone.utc)

    temp_dir = os.path.join(os.getcwd(), r"data/")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    partner_codes = Config.PARTNER_CODES.split(",")

    # Process notebooks for each partner
    # For each daily and monthly email, it is expected there is configuration per partner
    # e.g Config.VS_DAILY_RECONCILIATION_RECIPIENTS, Config.CSO_DAILY_RECONCILIATION_RECIPIENTS
    for code in partner_codes:
        for subdir in ["daily", "monthly"]:
            process_partner_notebooks(subdir, temp_dir, code)

    # process weekly pay notebook separate from partner notebooks
    process_notebooks("weekly", temp_dir)

    end_time = datetime.now(tz=timezone.utc)
    logging.info("job - jupyter notebook report completed in: %s", end_time - start_time)
    sys.exit()
