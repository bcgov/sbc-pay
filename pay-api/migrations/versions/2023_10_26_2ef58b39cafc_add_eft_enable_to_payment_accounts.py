"""18099-eft allowed flag

Revision ID: 2ef58b39cafc
Revises: 194cdd7cf986
Create Date: 2023-10-26 13:31:50.959562

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ef58b39cafc'
down_revision = '194cdd7cf986'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payment_accounts', sa.Column('eft_enable', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade():
    op.drop_column('payment_accounts', 'eft_enable')
