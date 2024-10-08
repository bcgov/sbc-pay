"""Adding disbursement_date column to eft_refunds

Revision ID: d1996caed682
Revises: f78095de8cfc
Create Date: 2024-10-08 11:48:33.350794

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'd1996caed682'
down_revision = 'f78095de8cfc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.drop_column('disbursement_date')
