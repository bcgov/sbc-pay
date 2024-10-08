"""Add in overdue notification date, for debugging also so we don't send multiples.

Revision ID: 1d5b66ef7f81
Revises: 4e57f6cf649c
Create Date: 2024-07-30 14:47:23.187621

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = "1d5b66ef7f81"
down_revision = "4e57f6cf649c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=60000;")
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("overdue_notification_date", sa.Date(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_column("overdue_notification_date")
