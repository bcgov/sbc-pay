"""new error codes

Revision ID: f74980cff974
Revises: 643790dd3334
Create Date: 2021-09-30 20:29:33.498824

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "f74980cff974"
down_revision = "643790dd3334"
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
                "code": "RS_DOESNT_EXIST",
                "title": "Routing slip number has not been found",
                "detail": "Routing slip number has not been found",
            },
            {
                "code": "RS_NOT_ACTIVE",
                "title": "This Routing Slip is not active",
                "detail": "This Routing Slip is not active",
            },
        ],
    )


def downgrade():
    op.execute(
        "DELETE FROM error_codes where code in ('RS_NOT_ACTIVE','RS_DOESNT_EXIST')"
    )
