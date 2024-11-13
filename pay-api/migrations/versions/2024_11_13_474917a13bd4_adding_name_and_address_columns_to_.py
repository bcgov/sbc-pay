"""Adding name and address columns to routing_slips

Revision ID: 474917a13bd4
Revises: 0f02d5964a63
Create Date: 2024-11-13 09:52:24.121948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '474917a13bd4'
down_revision = '0f02d5964a63'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(length=50), nullable=False))
        batch_op.add_column(sa.Column('street', sa.String(length=100), nullable=False))
        batch_op.add_column(sa.Column('street_additional', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('city', sa.String(length=50), nullable=False))
        batch_op.add_column(sa.Column('region', sa.String(length=50), nullable=False))
        batch_op.add_column(sa.Column('postal_code', sa.String(length=20), nullable=False))
        batch_op.add_column(sa.Column('country', sa.String(length=50), nullable=False))
        batch_op.add_column(sa.Column('delivery_instructions', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.drop_column('name')
        batch_op.drop_column('street')
        batch_op.drop_column('street_additional')
        batch_op.drop_column('city')
        batch_op.drop_column('region')
        batch_op.drop_column('postal_code')
        batch_op.drop_column('country')
        batch_op.drop_column('delivery_instructions')
