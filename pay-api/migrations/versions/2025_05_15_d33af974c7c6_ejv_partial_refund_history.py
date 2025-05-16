"""add missing columns to refunds_partial_history

Revision ID: d33af974c7c6
Revises: 0b7e98fdc955
Create Date: 2025-05-15 13:25:54.091995

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'd33af974c7c6'
down_revision = '0b7e98fdc955'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "refunds_partial_history", sa.Column("status", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "refunds_partial_history", sa.Column("gl_error", sa.String(length=250), nullable=True)
    )


def downgrade():
    op.drop_column("refunds_partial_history", "status")
    op.drop_column("refunds_partial_history", "gl_error")
