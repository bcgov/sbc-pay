"""Update error messages.

Revision ID: c61e4c535a15
Revises: 6970ffbdd50e
Create Date: 2022-07-13 22:15:06.146009

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "c61e4c535a15"
down_revision = "6970ffbdd50e"
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
        "delete from error_codes where code in ('BCOL_ACCOUNT_CLOSED', 'BCOL_USER_REVOKED', 'BCOL_ACCOUNT_REVOKED', 'BCOL_ERROR') "
    )
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "BCOL_ACCOUNT_CLOSED",
                "title": "BC Online account closed",
                "detail": "This BC Online account has been closed."
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/><br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca",
            },
            {
                "code": "BCOL_USER_REVOKED",
                "title": "BC Online user revoked",
                "detail": "This BC Online user has been revoked. "
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/><br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca",
            },
            {
                "code": "BCOL_ACCOUNT_REVOKED",
                "title": "BC Online account revoked",
                "detail": "This BC Online account has been revoked. "
                "<br/>Please contact the help desk to resolve this issue. "
                "<br/><br/>SERVICE BC HELP DESK: "
                "<br/>Toll-free: 1-800-663-6102 (Canada and USA only)"
                "<br/>Fax: (250) 952-6115"
                "<br/>Email: bcolhelp@gov.bc.ca",
            },
            {
                "code": "BCOL_ERROR",
                "title": "Error",
                "detail": "An error occurred during the BC Online transaction. "
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
