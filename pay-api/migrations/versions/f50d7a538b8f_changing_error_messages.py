"""changing_error_messages

Revision ID: f50d7a538b8f
Revises: 6ba89cd39cc8
Create Date: 2020-05-11 10:59:14.610738

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "f50d7a538b8f"
down_revision = "6ba89cd39cc8"
branch_labels = None
depends_on = None


def upgrade():
    error_code_table = table(
        "error_code",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    op.execute(
        "delete from error_code where code in ('BCOL_ACCOUNT_CLOSED', 'BCOL_USER_REVOKED', 'BCOL_ACCOUNT_REVOKED', 'BCOL_ERROR') "
    )
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "BCOL_ACCOUNT_CLOSED",
                "title": "BC Online account closed",
                "detail": "This BC Online account has been closed."
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca.",
            },
            {
                "code": "BCOL_USER_REVOKED",
                "title": "BC Online user revoked",
                "detail": "This BC Online user has been revoked. "
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca.",
            },
            {
                "code": "BCOL_ACCOUNT_REVOKED",
                "title": "BC Online account revoked",
                "detail": "This BC Online account has been revoked. "
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca.",
            },
            {
                "code": "BCOL_ERROR",
                "title": "Error",
                "detail": "An error occurred during the BC Online transaction. "
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca.",
            },
        ],
    )


def downgrade():
    pass
