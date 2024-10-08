"""add refund date to invoices

Revision ID: 0a3ad7c041f6
Revises: e296910623cd
Create Date: 2023-02-23 09:49:57.642039

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0a3ad7c041f6"
down_revision = "e296910623cd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=20000;")
    op.add_column("invoices", sa.Column("refund_date", sa.DateTime(), nullable=True))


def downgrade():
    op.execute("set statement_timeout=20000;")
    op.drop_column("invoice", "refund_date")
