"""Adding refund_method to eft_refunds

Revision ID: 48f199450139
Revises: dd1ed43ad732
Create Date: 2025-03-12 14:03:10.806089

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '48f199450139'
down_revision = 'dd1ed43ad732'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refund_method', sa.String(length=25), nullable=True))
        batch_op.add_column(sa.Column('cheque_status', sa.String(length=25), nullable=True))
        batch_op.add_column(sa.Column('entity_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('street', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('street_additional', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('city', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('region', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('postal_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('country', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('delivery_instructions', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.drop_column('refund_method')
        batch_op.drop_column('cheque_status')
        batch_op.drop_column('delivery_instructions')
        batch_op.drop_column('country')
        batch_op.drop_column('postal_code')
        batch_op.drop_column('region')
        batch_op.drop_column('city')
        batch_op.drop_column('street_additional')
        batch_op.drop_column('street')
        batch_op.drop_column('entity_name')
