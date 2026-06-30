"""add_comments_to_pay_admin_tables

Revision ID: 9b1c4d7e8f90
Revises: cb622dbbf69d
Create Date: 2026-06-08 15:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b1c4d7e8f90"
down_revision = "cb622dbbf69d"
branch_labels = None
depends_on = None


def upgrade():
    """Add comments columns to pay-admin tables and their history tables."""
    for table_name in ("corp_types", "distribution_codes", "fee_codes", "fee_schedules", "filing_types"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("comments", sa.String(length=250), nullable=True))

    for history_table_name in (
        "corp_types_history",
        "distribution_codes_history",
        "fee_codes_history",
        "fee_schedules_history",
        "filing_types_history",
    ):
        with op.batch_alter_table(history_table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("comments", sa.String(length=250), nullable=True))


def downgrade():
    """Drop comments columns from pay-admin tables and their history tables."""
    for history_table_name in (
        "filing_types_history",
        "fee_schedules_history",
        "fee_codes_history",
        "distribution_codes_history",
        "corp_types_history",
    ):
        with op.batch_alter_table(history_table_name, schema=None) as batch_op:
            batch_op.drop_column("comments")

    for table_name in ("filing_types", "fee_schedules", "fee_codes", "distribution_codes", "corp_types"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("comments")
