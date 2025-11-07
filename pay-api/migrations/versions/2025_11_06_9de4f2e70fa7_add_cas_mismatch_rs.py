"""Add cas_mismatch column to Routing Slip

Revision ID: 9de4f2e70fa7
Revises: 725543789c2a
Create Date: 2025-11-06 17:10:14.919060

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '9de4f2e70fa7'
down_revision = '725543789c2a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "routing_slips", sa.Column("cas_mismatch", sa.Boolean(), nullable=True)
    )


def downgrade():
    op.drop_column("routing_slips", "cas_mismatch")
