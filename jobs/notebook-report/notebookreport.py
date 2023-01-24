"""The Notebook Report - This module is the API for the Pay Notebook Report."""

import ast
import fnmatch
import logging
import os
import smtplib
import sys
import traceback
from datetime import date, datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import papermill as pm
from flask import Flask, current_app

from config import Config
from util.logging import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first

# Notebook Scheduler
# ---------------------------------------
# This script helps with the automated processing of Jupyter Notebooks via
# papermill (https://github.com/nteract/papermill/)


def create_app(config=Config):
    """Create app."""
    app = Flask(__name__)
    app.config.from_object(config)
    # db.init_app(app)
    app.app_context().push()
    current_app.logger.debug('created the Flask App and pushed the App Context')

    return app


def findfiles(directory, pattern):
    """Find files matched."""
    for filename in os.listdir(directory):
        if fnmatch.fnmatch(filename.lower(), pattern):
            yield os.path.join(directory, filename)


def send_email(file_processing, emailtype, errormessage):
    """Send email for results."""
    message = MIMEMultipart()
    date_str = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
    ext = ''
    if not Config.ENVIRONMENT == 'prod':
        ext = ' on ' + Config.ENVIRONMENT

    if emailtype == 'ERROR':
        subject = "Notebook Report Error '" + file_processing + "' on " + date_str + ext
        recipients = Config.ERROR_EMAIL_RECIPIENTS
        message.attach(MIMEText('ERROR!!! \n' + errormessage, 'plain'))
    else:
        if 'reconciliation_details' in file_processing:
            subject = 'Daily Reconciliation Stats ' + date_str + ext
            filenames = ['daily_reconciliation_' + date_str + '.csv']
            recipients = Config.DAILY_RECONCILIATION_RECIPIENTS
        elif 'pay' in file_processing:
            subject = 'Weekly PAY Stats till ' + date_str + ext
            filenames = ['weekly_pay_stats_till_' + date_str + '.csv']
            recipients = Config.WEEKLY_PAY_RECIPIENTS
        elif 'reconciliation_summary' in file_processing:
            year_month = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m')
            subject = 'Monthly Reconciliation Stats ' + year_month + ext
            filenames = ['monthly_reconciliation_summary_' + year_month + '.csv',
                         'monthly_reconciliation_disbursed_' + year_month + '.csv']
            recipients = Config.MONTHLY_RECONCILIATION_RECIPIENTS

    # Add body to email
    message.attach(MIMEText('Please see attached.', 'plain'))

    for file in filenames:
        part = MIMEBase('application', 'octet-stream')
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {file}',
        )
        file = os.path.join(os.getcwd(), r'data/') + file
        with open(file, 'rb') as attachment:
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        message.attach(part)

    message['Subject'] = subject
    server = smtplib.SMTP(Config.EMAIL_SMTP)
    email_list = recipients.strip('][').split(', ')
    logging.info('Email recipients list is: %s', email_list)
    server.sendmail(Config.SENDER_EMAIL, email_list, message.as_string())
    logging.info("Email with subject \'%s\' has been sent successfully!", subject)
    server.quit()


def processnotebooks(notebookdirectory, data_dir):
    """Process Notebook."""
    logging.info('Start processing directory: %s', notebookdirectory)

    try:
        weekly_report_dates = ast.literal_eval(Config.WEEKLY_REPORT_DATES)
        monthly_report_dates = ast.literal_eval(Config.MONTHLY_REPORT_DATES)
    except Exception:  # noqa: B902
        logging.exception('Error: %s.', notebookdirectory)
        send_email(notebookdirectory, 'ERROR', traceback.format_exc())

    # Monday is 1 and Sunday is 7
    # First day of the month is 1
    if notebookdirectory == 'daily' \
            or (notebookdirectory == 'weekly' and date.today().isoweekday() in weekly_report_dates) \
            or (notebookdirectory == 'monthly' and date.today().day in monthly_report_dates):
        for file in findfiles(notebookdirectory, '*.ipynb'):
            try:
                pm.execute_notebook(file, data_dir + 'temp.ipynb', parameters=None)
                # send email to receivers and remove files/directories which we don't want to keep
                send_email(file, '', '')
                os.remove(data_dir + 'temp.ipynb')
            except Exception:  # noqa: B902
                logging.exception('Error: %s.', file)
                send_email(file, 'ERROR', traceback.format_exc())


if __name__ == '__main__':
    start_time = datetime.utcnow()

    temp_dir = os.path.join(os.getcwd(), r'data/')
    # Check if the subfolders for notebooks exist, and create them if they don't
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    for subdir in ['daily', 'weekly', 'monthly']:
        processnotebooks(subdir, temp_dir)

    end_time = datetime.utcnow()
    logging.info('job - jupyter notebook report completed in: %s', end_time - start_time)
    sys.exit()
