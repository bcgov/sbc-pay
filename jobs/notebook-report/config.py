import ast
import os

from dotenv import find_dotenv, load_dotenv

# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())


class Config(object):
    """Class configuring our environment variables in one defined place."""

    PROJECT_ROOT = os.getcwd()
    APP_FILE = os.getenv("APP_FILE", "")
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
    ERROR_EMAIL_RECIPIENTS = os.getenv("ERROR_EMAIL_RECIPIENTS", "")
    WEEKLY_PAY_RECIPIENTS = os.getenv("WEEKLY_PAY_RECIPIENTS", "")

    # MIGHT REMOVE THESE TWO:
    VS_DAILY_RECONCILIATION_RECIPIENTS = os.getenv("VS_DAILY_RECONCILIATION_RECIPIENTS", "")
    CSO_DAILY_RECONCILIATION_RECIPIENTS = os.getenv("CSO_DAILY_RECONCILIATION_RECIPIENTS", "")

    VS_RECONCILIATION_RECIPIENTS = os.getenv("VS_RECONCILIATION_RECIPIENTS", "")
    CSO_RECONCILIATION_RECIPIENTS = os.getenv("CSO_RECONCILIATION_RECIPIENTS", "")
    RPT_RECONCILIATION_RECIPIENTS = os.getenv("RPT_RECONCILIATION_RECIPIENTS", "")
    ESRA_RECONCILIATION_RECIPIENTS = os.getenv("ESRA_RECONCILIATION_RECIPIENTS", "")
    STRR_RECONCILIATION_RECIPIENTS = os.getenv("STRR_RECONCILIATION_RECIPIENTS", "")

    EMAIL_SMTP = os.getenv("EMAIL_SMTP", "")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "")

    WEEKLY_REPORT_DATES = ast.literal_eval(os.getenv("WEEKLY_REPORT_DATES", "[1]"))
    WEEKLY_RECONCILIATION_PARTNERS = os.getenv("WEEKLY_RECONCILIATION_PARTNERS", "STRR")
    MONTHLY_REPORT_DATES = ast.literal_eval(os.getenv("MONTHLY_REPORT_DATES", "[1]"))
    MONTHLY_RECONCILIATION_PARTNERS = os.getenv("MONTHLY_RECONCILIATION_PARTNERS", "CSO,VS,RPT,ESRA")

    PARTNER_CODES = os.getenv("PARTNER_CODES", "CSO,VS,RPT,ESRA,STRR")
    PARTNER_CODES_DISBURSEMENT = os.getenv("PARTNER_CODES_DISBURSEMENT", "CSO,VS,STRR")
    REPORT_API_URL = os.getenv("REPORT_API_URL", "") + os.getenv("REPORT_API_VERSION", "/api/v1")
    NOTEBOOK_SERVICE_ACCOUNT_ID = os.getenv("NOTEBOOK_SERVICE_ACCOUNT_ID", "")
    NOTEBOOK_SERVICE_ACCOUNT_SECRET = os.getenv("NOTEBOOK_SERVICE_ACCOUNT_SECRET", "")
    JWT_OIDC_ISSUER = os.getenv("JWT_OIDC_ISSUER", "")
    # Used for local dev runs.
    DISABLE_EMAIL = os.getenv("DISABLE_EMAIL", "false").lower() == "true"

    PAY_USER = os.getenv("PAY_USER", "")
    PAY_PASSWORD = os.getenv("PAY_PASSWORD", "")
    PAY_DB_NAME = os.getenv("PAY_DB_NAME", "")
    PAY_HOST = os.getenv("PAY_HOST", "")
    PAY_PORT = os.getenv("PAY_PORT", "5432")
    SQLALCHEMY_DATABASE_URI = "postgresql://{user}:{password}@{host}:{port}/{name}".format(
        user=PAY_USER,
        password=PAY_PASSWORD,
        host=PAY_HOST,
        port=int(PAY_PORT),
        name=PAY_DB_NAME,
    )
    OVERRIDE_CURRENT_DATE = os.getenv("OVERRIDE_CURRENT_DATE", "")
