"""add details for RS_CANT_LINK_NSF

Revision ID: 059abb33d3c3
Revises: dbe9dc38ac33
Create Date: 2022-04-27 07:00:25.281053

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "059abb33d3c3"
down_revision = "dbe9dc38ac33"
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
                "code": "RS_CANT_LINK_NSF",
                "title": "Routing Slip cannot be linked.",
                "detail": "Linking cannot be performed since the routing slip is NSF. It can only be linked to.",
            }
        ],
    )


def downgrade():
    op.execute("DELETE FROM error_codes where code in ('RS_CANT_LINK_NSF')")
