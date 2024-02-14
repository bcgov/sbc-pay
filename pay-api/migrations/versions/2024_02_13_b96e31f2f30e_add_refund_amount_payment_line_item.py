"""empty message

Revision ID: b96e31f2f30e
Revises: 03884e4187de
Create Date: 2024-02-13 16:27:37.024941

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b96e31f2f30e'
down_revision = '03884e4187de'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payment_line_items', sa.Column('refund_amount', sa.Numeric(), nullable=True))


def downgrade():
    op.drop_column('payment_line_items', 'refund_amount')
