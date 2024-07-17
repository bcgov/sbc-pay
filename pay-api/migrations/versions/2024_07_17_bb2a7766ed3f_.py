"""Add in disbursement_date column to eft_credit_invoice_links, so we can handle disbursements.

Revision ID: bb2a7766ed3f
Revises: f98666d9809a
Create Date: 2024-07-17 07:13:27.018483

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bb2a7766ed3f'
down_revision = 'f98666d9809a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_credit_invoice_links', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_date', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('eft_credit_invoice_links', schema=None) as batch_op:
        batch_op.drop_column('disbursement_date')
