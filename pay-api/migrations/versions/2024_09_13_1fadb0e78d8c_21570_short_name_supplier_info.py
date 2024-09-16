"""21570-Short-name-supplier-info

Revision ID: 1fadb0e78d8c
Revises: 2097573390f1
Create Date: 2024-09-13 11:28:29.568578

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '1fadb0e78d8c'
down_revision = '2097573390f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cas_supplier_number', sa.String(25), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(100), nullable=True))


def downgrade():
    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.drop_column('cas_supplier_number')
        batch_op.drop_column('email')
