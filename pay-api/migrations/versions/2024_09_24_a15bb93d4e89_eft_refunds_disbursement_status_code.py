"""Adding disbursement_status_code column to eft_refunds

Revision ID: a15bb93d4e89
Revises: 1fadb0e78d8c
Create Date: 2024-09-24 00:31:32.880154

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'a15bb93d4e89'
down_revision = '29f59e6f147b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_status_code', sa.String(length=20), nullable=True))
        batch_op.create_foreign_key(None, 'disbursement_status_codes', ['disbursement_status_code'], ['code'])


def downgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('disbursement_status_code')
