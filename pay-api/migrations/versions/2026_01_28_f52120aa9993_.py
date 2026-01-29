"""Add restrict_ejv column to payment_accounts table.

Revision ID: f52120aa9993
Revises: 3f51ab8b4a10
Create Date: 2026-01-28 14:01:12.660238

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'f52120aa9993'
down_revision = '3f51ab8b4a10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('restrict_ejv', sa.Boolean(), server_default='f', nullable=False))

    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('restrict_ejv', sa.Boolean(), server_default='f', autoincrement=False, nullable=False))


def downgrade():
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.drop_column('restrict_ejv')

    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.drop_column('restrict_ejv')
