"""Migration for Routing slip status COMPLETE.

Revision ID: 7aff4af4be85
Revises: 6a6b042b831a
Create Date: 2022-05-30 08:23:00.535893

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "7aff4af4be85"
down_revision = "6a6b042b831a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE routing_slips set status = 'COMPLETE' where remaining_amount < 0.01 and status = 'ACTIVE'"
    )


def downgrade():
    op.execute(
        "UPDATE routing_slips set status = 'ACTIVE' where remaining_amount < 0.01 and status = 'COMPLETE'"
    )
