"""Add Non-Sufficient Funds table to store Non-Sufficient Funds invoices

Revision ID: b65365f7852b
Revises: ff245db0cf76
Create Date: 2023-12-05 12:28:27.025012

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b65365f7852b"
down_revision = "ff245db0cf76"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "non_sufficient_funds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("description", sa.String(length=50), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("non_sufficient_funds")
