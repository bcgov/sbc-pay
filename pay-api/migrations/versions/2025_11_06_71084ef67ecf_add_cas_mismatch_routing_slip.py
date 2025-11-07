"""Add cas_mismatch column to Routing Slip

Revision ID: 71084ef67ecf
Revises: 51d45022f722
Create Date: 2025-11-06 16:18:02.010207

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '71084ef67ecf'
down_revision = '51d45022f722'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "routing_slips", sa.Column("cas_mismatch", sa.Boolean(), nullable=True)
    )


def downgrade():
    op.drop_column("routing_slips", "cas_mismatch")
