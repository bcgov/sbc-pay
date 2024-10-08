"""create insufficient fund bcol error

Revision ID: 872760122cc9
Revises: 20f0cfd54e81
Create Date: 2020-09-29 17:15:54.848026

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "872760122cc9"
down_revision = "20f0cfd54e81"
branch_labels = None
depends_on = None


def upgrade():
    error_code_table = table(
        "error_code",
        column("code", String),
        column("title", String),
        column("detail", String),
    )

    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "BCOL_ACCOUNT_INSUFFICIENT_FUNDS",
                "title": "Insufficient Funds",
                "detail": "This BC Online account has insufficient funds. "
                "<br/>Please add funds to the account. "
                "<br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca.",
            }
        ],
    )


def downgrade():
    op.execute("delete from error_code where code='BCOL_ACCOUNT_INSUFFICIENT_FUNDS'")
