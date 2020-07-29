"""merge heads

Revision ID: 7a316d48f9ae
Revises: 7ea7ba8fe991, a11be9fe1a6a
Create Date: 2020-07-28 13:53:09.606919

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a316d48f9ae'
down_revision = ('7ea7ba8fe991', 'a11be9fe1a6a')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
