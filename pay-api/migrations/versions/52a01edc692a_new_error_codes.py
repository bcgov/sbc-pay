"""new error codes

Revision ID: 52a01edc692a
Revises: d73cbcdd2f25
Create Date: 2022-03-15 07:27:05.819597

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "52a01edc692a"
down_revision = "d73cbcdd2f25"
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
                "code": "RS_IN_INVALID_STATUS",
                "title": "Routing Slip is in invalid status.",
                "detail": "Linking cannot be performed since the routing is not in a linkable status.",
            },
            {
                "code": "RS_INSUFFICIENT_FUNDS",
                "title": "Routing Slip has insufficient funds.",
                "detail": "This routing slip has been marked as Non-Sufficient Funds and can not be used for payment.",
            },
        ],
    )


def downgrade():

    op.execute(
        "DELETE FROM error_codes where code in ('RS_IN_INVALID_STATUS','RS_INSUFFICIENT_FUNDS')"
    )
