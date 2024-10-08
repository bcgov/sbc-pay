"""fas status changes

Revision ID: 2c1ecdec185a
Revises: f8408a4a782c
Create Date: 2022-01-05 20:26:15.392781

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "2c1ecdec185a"
down_revision = "f8408a4a782c"
branch_labels = None
depends_on = None


def upgrade():
    error_code_table = table(
        "error_codes",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "FAS_INVALID_RS_STATUS_CHANGE",
                "title": "Routing slip status transition is not allowed.",
                "detail": "Routing slip status transition is not allowed.",
            }
        ],
    )


def downgrade():
    op.execute(
        "delete from error_codes where code in ('FAS_INVALID_RS_STATUS_CHANGE') "
    )
