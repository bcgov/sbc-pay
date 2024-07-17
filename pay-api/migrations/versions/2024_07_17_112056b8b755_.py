"""Get rid of invoice batches, invoice batch links, eft gl transfers.

Revision ID: 112056b8b755
Revises: f98666d9809a
Create Date: 2024-07-17 07:37:52.834892

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '112056b8b755'
down_revision = 'f98666d9809a'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('invoice_batches')
    op.drop_table('invoice_batch_links')
    op.drop_table('eft_gl_transfers')
    op.create_table('partner_disbursements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('amount', sa.Numeric(), nullable=False),
    sa.Column('created_on', sa.DateTime(), nullable=False),
    sa.Column('disbursement_type', sa.String(length=50), nullable=False),
    sa.Column('feedback_on', sa.DateTime(), nullable=True),
    sa.Column('partner_code', sa.String(length=50), nullable=False),
    sa.Column('processed_on', sa.DateTime(), nullable=True),
    sa.Column('is_reversal', sa.Boolean(), nullable=False),
    sa.Column('source_gl', sa.String(length=50), nullable=False),
    sa.Column('status_code', sa.String(length=25), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('target_gl', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
     op.drop_table('partner_disbursements')
