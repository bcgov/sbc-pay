"""EFT Short name history short name refund.

Revision ID: 67407611eec8
Revises: 423a9f909079
Create Date: 2024-09-18 10:20:15.689980

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '67407611eec8'
down_revision = '423a9f909079'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_short_names_historical', schema=None) as batch_op:
        batch_op.add_column(sa.Column('eft_refund_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_eft_short_names_historical_eft_refund_id'), ['eft_refund_id'], unique=False)
        batch_op.create_foreign_key('eft_short_names_historical_eft_refund_id_fkey', 'eft_refunds', ['eft_refund_id'], ['id'])


def downgrade():
    with op.batch_alter_table('eft_short_names_historical', schema=None) as batch_op:
        batch_op.drop_constraint('eft_short_names_historical_eft_refund_id_fkey', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_eft_short_names_historical_eft_refund_id'))
        batch_op.drop_column('eft_refund_id')
