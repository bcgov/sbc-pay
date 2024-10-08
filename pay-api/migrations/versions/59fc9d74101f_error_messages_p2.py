"""Error Messages part2

Revision ID: 59fc9d74101f
Revises: c61e4c535a15
Create Date: 2022-07-14 15:53:47.895109

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "59fc9d74101f"
down_revision = "c61e4c535a15"
branch_labels = None
depends_on = None


def upgrade():
    error_code_table = table(
        "error_codes",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    op.execute(
        "delete from error_codes where code in ('BCOL_INVALID_ACCOUNT', 'BCOL_ACCOUNT_INSUFFICIENT_FUNDS') "
    )
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "BCOL_ACCOUNT_INSUFFICIENT_FUNDS",
                "title": "Insufficient Funds",
                "detail": "This BC Online account has insufficient funds. "
                "<br/>Please add funds to the account. "
                "<br/><br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca",
            },
            {
                "code": "BCOL_INVALID_ACCOUNT",
                "title": "BC Online account is invalid",
                "detail": "BC Online account is invalid."
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/><br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca",
            },
        ],
    )


def downgrade():
    pass
