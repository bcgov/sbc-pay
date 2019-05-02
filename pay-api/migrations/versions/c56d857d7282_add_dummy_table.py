"""add dummy table'

Revision ID: c56d857d7282
Revises: 
Create Date: 2019-05-02 09:01:33.666614

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c56d857d7282'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dummy',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('dummyname', sa.String(100), nullable=False)
    )


def downgrade():
    op.drop_table('dummy')
