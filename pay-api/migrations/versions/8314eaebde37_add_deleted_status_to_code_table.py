"""add_deleted_status_to_code_table

Revision ID: 8314eaebde37
Revises: bae02665e807
Create Date: 2019-10-07 13:26:59.246530

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "8314eaebde37"
down_revision = "bae02665e807"
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table(
        "status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(status_code_table, [{"code": "DELETED", "description": "Deleted"}])


def downgrade():
    op.execute("DELETE FROM status_code WHERE status_code = 'DELETED';")
