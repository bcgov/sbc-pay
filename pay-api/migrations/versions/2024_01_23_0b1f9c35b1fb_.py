"""Add cfs_account and modify invoice_number to be non-nullable in non_sufficient_funds table

Revision ID: 0b1f9c35b1fb
Revises: fccdab259e05
Create Date: 2024-01-23 14:26:29.427462

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0b1f9c35b1fb"
down_revision = "fccdab259e05"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "non_sufficient_funds",
        sa.Column(
            "cfs_account",
            sa.String(length=50),
            nullable=True,
            comment="CFS Account number",
        ),
    )
    op.alter_column(
        "non_sufficient_funds",
        "invoice_number",
        existing_type=sa.VARCHAR(length=50),
        nullable=False,
        existing_comment="CFS Invoice number",
    )


def downgrade():
    op.alter_column(
        "non_sufficient_funds",
        "invoice_number",
        existing_type=sa.VARCHAR(length=50),
        nullable=True,
        existing_comment="CFS Invoice number",
    )
    op.drop_column("non_sufficient_funds", "cfs_account")
