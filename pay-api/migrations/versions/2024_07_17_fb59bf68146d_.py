"""Add in receipt_number for eft_credit_invoice_links.

Revision ID: fb59bf68146d
Revises: 112056b8b755
Create Date: 2024-07-17 16:18:03.699828

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fb59bf68146d'
down_revision = '112056b8b755'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_credit_invoice_links', schema=None) as batch_op:
        batch_op.add_column(sa.Column('receipt_number', sa.String(length=50), nullable=False))

def downgrade():
    with op.batch_alter_table('eft_credit_invoice_links', schema=None) as batch_op:
        batch_op.drop_column('receipt_number')
