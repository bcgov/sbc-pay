import os
from dotenv import load_dotenv, find_dotenv

# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())


class Config(object):
    PROJECT_ROOT = os.getcwd()
    APP_FILE = os.getenv('APP_FILE', '')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', '')
    ERROR_EMAIL_RECIPIENTS = os.getenv('ERROR_EMAIL_RECIPIENTS', '')
    DAILY_RECONCILIATION_RECIPIENTS = os.getenv('DAILY_RECONCILIATION_RECIPIENTS', '')
    VS_DAILY_RECONCILIATION_RECIPIENTS = os.getenv('VS_DAILY_RECONCILIATION_RECIPIENTS', '')
    CSO_DAILY_RECONCILIATION_RECIPIENTS = os.getenv('CSO_DAILY_RECONCILIATION_RECIPIENTS', '')
    WEEKLY_PAY_RECIPIENTS = os.getenv('WEEKLY_PAY_RECIPIENTS', '')
    MONTHLY_RECONCILIATION_RECIPIENTS = os.getenv('MONTHLY_RECONCILIATION_RECIPIENTS', '')
    VS_MONTHLY_RECONCILIATION_RECIPIENTS = os.getenv('VS_MONTHLY_RECONCILIATION_RECIPIENTS', '')
    CSO_MONTHLY_RECONCILIATION_RECIPIENTS = os.getenv('CSO_MONTHLY_RECONCILIATION_RECIPIENTS', '')
    EMAIL_SMTP = os.getenv('EMAIL_SMTP', '')
    ENVIRONMENT = os.getenv('ENVIRONMENT', '')
    WEEKLY_REPORT_DATES = os.getenv('WEEKLY_REPORT_DATES', '[1]')
    MONTHLY_REPORT_DATES = os.getenv('MONTHLY_REPORT_DATES', '[1]')
    PARTNER_CODES = os.getenv('PARTNER_CODES', 'CSO,VS,RPT,ESRA')

    # POSTGRESQL
    PAY_USER = os.getenv('PAY_USER', '')
    PAY_PASSWORD = os.getenv('PAY_PASSWORD', '')
    PAY_DB_NAME = os.getenv('PAY_DB_NAME', '')
    PAY_HOST = os.getenv('PAY_HOST', '')
    PAY_PORT = os.getenv('PAY_PORT', '5432')
    SQLALCHEMY_DATABASE_URI = 'postgresql://{user}:{password}@{host}:{port}/{name}'.format(
        user=PAY_USER,
        password=PAY_PASSWORD,
        host=PAY_HOST,
        port=int(PAY_PORT),
        name=PAY_DB_NAME,
    )
