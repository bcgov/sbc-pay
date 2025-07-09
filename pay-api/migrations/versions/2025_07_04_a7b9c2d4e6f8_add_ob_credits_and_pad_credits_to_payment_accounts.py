"""add ob_credit and pad_credit to payment_accounts

Revision ID: a7b9c2d4e6f8
Revises: afccd441770e
Create Date: 2025-01-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a7b9c2d4e6f8'
down_revision = 'b927265cf3a1'
branch_labels = None
depends_on = None


def upgrade():
    """Add ob_credit and pad_credit columns to payment_accounts table and drop credit column."""
    op.add_column('payment_accounts', sa.Column('ob_credit', sa.Numeric(19, 2), nullable=True))
    op.add_column('payment_accounts', sa.Column('pad_credit', sa.Numeric(19, 2), nullable=True))
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ob_credit', sa.Numeric(19, 2), nullable=True))
        batch_op.add_column(sa.Column('pad_credit', sa.Numeric(19, 2), nullable=True))
        batch_op.drop_column('credit')

    op.drop_column('payment_accounts', 'credit')
    op.add_column('credits', sa.Column('cfs_site', sa.String(length=50), nullable=True))


def downgrade():
    """Remove ob_credit and pad_credit columns and restore credit column from payment_accounts table."""
    op.drop_column('credits', 'cfs_site') 
    op.add_column('payment_accounts', sa.Column('credit', sa.Numeric(19, 2), nullable=True))
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.drop_column('ob_credit')
        batch_op.drop_column('pad_credit')
        batch_op.add_column(sa.Column('credit', sa.Numeric(19, 2), nullable=True))

    op.drop_column('payment_accounts', 'ob_credit')
    op.drop_column('payment_accounts', 'pad_credit') 
