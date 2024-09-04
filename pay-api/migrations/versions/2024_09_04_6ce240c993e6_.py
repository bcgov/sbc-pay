"""Adding disbursement_status_code column to eft_refunds

Revision ID: 6ce240c993e6
Revises: 2097573390f1
Create Date: 2024-09-04 10:52:51.435202

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '6ce240c993e6'
down_revision = '2097573390f1'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=900000;")
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_status_code', sa.String(length=20), nullable=True))
        batch_op.create_foreign_key(None, 'disbursement_status_codes', ['disbursement_status_code'], ['code'])


def downgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('disbursement_status_code')
