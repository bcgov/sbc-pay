"""Add restrict_pad column to payment_accounts table.

Revision ID: e3b8c1d4f7a2
Revises: d9f4a7e2c8b6
Create Date: 2026-11-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.migration_utils import column_exists


revision = "e3b8c1d4f7a2"
down_revision = "d9f4a7e2c8b6"
branch_labels = None
depends_on = None


def upgrade():
    if not column_exists("payment_accounts", "restrict_pad"):
        with op.batch_alter_table("payment_accounts", schema=None) as batch_op:
            batch_op.add_column(sa.Column("restrict_pad", sa.Boolean(), server_default="f", nullable=False))

    if not column_exists("payment_accounts_history", "restrict_pad"):
        with op.batch_alter_table("payment_accounts_history", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("restrict_pad", sa.Boolean(), server_default="f", autoincrement=False, nullable=False)
            )

    op.execute("delete from error_codes where code = 'PAD_PAYMENT_METHOD_RESTRICTED'")
    op.execute(
        "insert into error_codes (code, title, detail) values ("
        "'PAD_PAYMENT_METHOD_RESTRICTED', "
        "'Pre-authorized debit is no longer available', "
        "'Pre-authorized debit is no longer available on this account. "
        "An account administrator needs to choose a new payment method in Account Settings.')"
    )


def downgrade():
    op.execute("delete from error_codes where code = 'PAD_PAYMENT_METHOD_RESTRICTED'")

    if column_exists("payment_accounts_history", "restrict_pad"):
        with op.batch_alter_table("payment_accounts_history", schema=None) as batch_op:
            batch_op.drop_column("restrict_pad")

    if column_exists("payment_accounts", "restrict_pad"):
        with op.batch_alter_table("payment_accounts", schema=None) as batch_op:
            batch_op.drop_column("restrict_pad")
