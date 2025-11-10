"""empty message

Revision ID: 76b874c82ad6
Revises: 725543789c2a
Create Date: 2025-11-10 11:21:10.899436

"""
from alembic import op
import sqlalchemy as sa

revision = '76b874c82ad6'
down_revision = '9de4f2e70fa7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('requester_email', sa.String(length=100), nullable=True))

def downgrade():
    with op.batch_alter_table('refunds', schema=None) as batch_op:
        batch_op.drop_column('requester_email')
