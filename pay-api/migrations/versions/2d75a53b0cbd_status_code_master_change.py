"""status_code_master_change

Revision ID: 2d75a53b0cbd
Revises: f35e4c5621ac
Create Date: 2019-07-22 16:11:14.296001

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "2d75a53b0cbd"
down_revision = "f35e4c5621ac"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "payment_transaction",
        "status_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )

    status_code_table = table(
        "status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table,
        [{"code": "EVENT_FAILED", "description": "Event Notification Failed"}],
    )


def downgrade():
    op.execute("DELETE FROM status_code WHERE code = 'EVENT_FAILED';")
    op.alter_column(
        "payment_transaction",
        "status_code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
