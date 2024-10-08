"""bcol_invalid_account_error

Revision ID: 099ba5cf19a3
Revises: e67a61c01cbb
Create Date: 2021-06-25 15:33:24.872754

"""

from alembic import op
import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "099ba5cf19a3"
down_revision = "e67a61c01cbb"
branch_labels = None
depends_on = None


def upgrade():
    error_code_table = table(
        "error_codes",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    op.execute("delete from error_codes where code in ('BCOL_INVALID_ACCOUNT') ")
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "BCOL_INVALID_ACCOUNT",
                "title": "BC Online account is invalid",
                "detail": "BC Online account is invalid."
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca.",
            }
        ],
    )


def downgrade():
    op.execute("delete from error_codes where code in ('BCOL_INVALID_ACCOUNT') ")
