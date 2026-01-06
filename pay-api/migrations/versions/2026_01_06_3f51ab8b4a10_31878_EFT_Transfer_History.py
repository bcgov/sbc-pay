"""31878 - EFT Short name historical comment field

Revision ID: 3f51ab8b4a10
Revises: 76b874c82ad6
Create Date: 2026-01-06 10:19:16.809492

"""
from alembic import op
import sqlalchemy as sa

revision = '3f51ab8b4a10'
down_revision = '76b874c82ad6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_short_names_historical', schema=None) as batch_op:
        batch_op.add_column(sa.Column('comment', sa.String(length=250), nullable=True))

def downgrade():
    with op.batch_alter_table('eft_short_names_historical', schema=None) as batch_op:
        batch_op.drop_column('comment')
