"""Get rid of invoice batches, invoice batch links, eft gl transfers. Add in partner disbursements.

Revision ID: 112056b8b755
Revises: f98666d9809a
Create Date: 2024-07-17 07:37:52.834892

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '112056b8b755'
down_revision = 'f98666d9809a'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('invoice_batches')
    op.drop_table('invoice_batch_links')
    op.drop_table('eft_gl_transfers')
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_reversal_date', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('disbursement_reversal_date')
