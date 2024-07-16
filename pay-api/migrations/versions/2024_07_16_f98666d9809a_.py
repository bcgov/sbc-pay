"""Add in composite index for invoice_status_code and payment_account_id so our payment blocker check is fast.

Revision ID: f98666d9809a
Revises: f921d5e32835
Create Date: 2024-07-16 14:26:07.469225

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f98666d9809a'
down_revision = 'f921d5e32835'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.create_index('idx_invoice_invoice_status_code_payment_account_idx', ['payment_account_id', 'invoice_status_code'], unique=False)

def downgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_index('idx_invoice_invoice_status_code_payment_account_idx')
