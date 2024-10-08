"""Adding invoice_number column to non_sufficient_funds table

Revision ID: fccdab259e05
Revises: b65365f7852b
Create Date: 2024-01-22 17:13:44.797905

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fccdab259e05"
down_revision = "b65365f7852b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "non_sufficient_funds",
        sa.Column("invoice_number", sa.String(length=50), comment="CFS Invoice number"),
    )
    op.create_index(
        op.f("ix_non_sufficient_funds_invoice_number"),
        "non_sufficient_funds",
        ["invoice_number"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_non_sufficient_funds_invoice_number"),
        table_name="non_sufficient_funds",
    )
    op.drop_column("non_sufficient_funds", "invoice_number")
