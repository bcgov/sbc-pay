"""add expense authority email list

Revision ID: 00175c87b22b
Revises: 88743c788c02
Create Date: 2024-07-11 13:22:56.261585

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '00175c87b22b'
down_revision = '88743c788c02'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('eft_refund_email_list',
                    sa.Column('first_name', sa.String(25), nullable=True),
                    sa.Column('last_name', sa.String(25), nullable=True),
                    sa.Column('email', sa.String(25), nullable=True),
                    sqlite_autoincrement=True
                    )
def downgrade():
    op.drop_table('eft_refund_email_list')
