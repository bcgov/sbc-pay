"""fix RS_CANT_LINK_NSF description

Revision ID: 175c11863186
Revises: 2ccbd2aad2dc
Create Date: 2022-05-03 16:06:42.663506

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "175c11863186"
down_revision = "2ccbd2aad2dc"
branch_labels = None
depends_on = None


def upgrade():
    # Delete existing code.
    op.execute("DELETE FROM error_codes where code in ('RS_CANT_LINK_NSF')")
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
                "code": "RS_CANT_LINK_NSF",
                "title": "Routing Slip cannot be linked.",
                "detail": "Linking cannot be performed since the Routing slip is NSF.",
            }
        ],
    )


def downgrade():
    # Delete existing code.
    op.execute("DELETE FROM error_codes where code in ('RS_CANT_LINK_NSF')")
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
                "code": "RS_CANT_LINK_NSF",
                "title": "Routing Slip cannot be linked.",
                "detail": "Linking cannot be performed since the routing slip is NSF. It can only be linked to.",
            }
        ],
    )
