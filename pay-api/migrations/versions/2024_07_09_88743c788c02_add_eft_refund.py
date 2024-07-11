"""add_eft_refund

Revision ID: 88743c788c02
Revises: 0672573574f6
Create Date: 2024-07-09 15:23:04.800731

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '88743c788c02'
down_revision = '0672573574f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('eft_refunds',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('short_name_id', sa.Integer(), nullable=False),
                    sa.Column('auth_account_id', sa.String(length=50), nullable=False),
                    sa.Column('refund_amount', sa.Numeric(), nullable=False),
                    sa.Column('cas_supplier_number', sa.String(length=25), nullable=False),
                    sa.Column('created_on', sa.DateTime(), nullable=False),
                    sa.Column('refund_email', sa.String(length=100), nullable=False),
                    sa.Column('comment', sa.String(), nullable=True),
                    sa.Column('status', sa.String(length=25), nullable=True),
                    sa.Column('updated_by', sa.String(length=100), nullable=True),
                    sa.Column('updated_by_name', sa.String(length=100), nullable=True),
                    sa.Column('updated_on', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['short_name_id'], ['eft_short_names.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sqlite_autoincrement=True
                    )
def downgrade():
    op.drop_table('eft_refunds')
