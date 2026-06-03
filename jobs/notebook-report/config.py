"""Config file for the application."""

import ast
import os

from cloud_sql_connector import DBConfig, getconn
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


class Config:
    """Class configuring our environment variables in one defined place."""

    PROJECT_ROOT = os.getcwd()
    APP_FILE = "notebookreport.py"
    ERROR_EMAIL_RECIPIENTS = os.getenv("ERROR_EMAIL_RECIPIENTS", "")
    WEEKLY_PAY_RECIPIENTS = os.getenv("WEEKLY_PAY_RECIPIENTS", "")

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
    PARTNER_CODES_DISBURSEMENT = os.getenv("PARTNER_CODES_DISBURSEMENT", "CSO,VS,STRR,ESRA")
    REPORT_API_URL = os.getenv("REPORT_API_URL", "") + os.getenv("REPORT_API_VERSION", "/api/v1")
    NOTIFY_API_URL = os.getenv("NOTIFY_API_URL", "") + os.getenv("NOTIFY_API_VERSION", "/api/v1") + "/notify/"
    NOTEBOOK_SERVICE_ACCOUNT_ID = os.getenv("NOTEBOOK_SERVICE_ACCOUNT_ID", "")
    NOTEBOOK_SERVICE_ACCOUNT_SECRET = os.getenv("NOTEBOOK_SERVICE_ACCOUNT_SECRET", "")
    JWT_OIDC_ISSUER = os.getenv("JWT_OIDC_ISSUER", "")
    # Used for local dev runs.
    DISABLE_EMAIL = os.getenv("DISABLE_EMAIL", "false").lower() == "true"

    # POSTGRESQL
    DB_USER = os.getenv("PAY_USER", "")
    DB_NAME = os.getenv("PAY_DB_NAME", "")

    # Cloud SQL connector support
    CLOUDSQL_INSTANCE_CONNECTION_NAME = os.getenv("CLOUDSQL_INSTANCE", "")
    DB_IP_TYPE = os.getenv("DATABASE_IP_TYPE", "private").lower()

    if CLOUDSQL_INSTANCE_CONNECTION_NAME:
        SQLALCHEMY_DATABASE_URI = "postgresql+pg8000://"
    else:
        DB_PASSWORD = os.getenv("PAY_PASSWORD", "")
        DB_HOST = os.getenv("PAY_HOST", "")
        DB_PORT = os.getenv("PAY_PORT", "5432")
        SQLALCHEMY_DATABASE_URI = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    OVERRIDE_CURRENT_DATE = os.getenv("OVERRIDE_CURRENT_DATE", "")


def get_conn():
    """Return a new DBAPI connection via Cloud SQL Connector."""
    config = DBConfig(
        instance_name=Config.CLOUDSQL_INSTANCE_CONNECTION_NAME,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        ip_type=Config.DB_IP_TYPE,
        schema="public",
    )
    return getconn(config)
