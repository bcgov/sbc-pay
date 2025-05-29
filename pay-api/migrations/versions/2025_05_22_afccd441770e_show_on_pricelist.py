"""empty message

Revision ID: afccd441770e
Revises: d33af974c7c6
Create Date: 2025-05-22 08:35:59.286331

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'afccd441770e'
down_revision = 'd33af974c7c6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fee_schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_on_pricelist', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))

def downgrade():
    with op.batch_alter_table('fee_schedules', schema=None) as batch_op:
        batch_op.drop_column('show_on_pricelist')
