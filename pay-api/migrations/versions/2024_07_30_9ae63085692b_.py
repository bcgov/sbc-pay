"""Add in field for overdue_reminder

Revision ID: 9ae63085692b
Revises: 4e57f6cf649c
Create Date: 2024-07-30 14:39:49.673357

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '9ae63085692b'
down_revision = '4e57f6cf649c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('statements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('overdue_reminder', sa.Boolean(), nullable=False))


def downgrade():
    with op.batch_alter_table('statements', schema=None) as batch_op:
        batch_op.drop_column('overdue_reminder')
