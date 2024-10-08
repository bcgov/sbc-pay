"""Add is_consolidated and created_on columns to invoice_references

Revision ID: 2097573390f1
Revises: fc32e7db4493
Create Date: 2024-08-29 12:01:51.061253

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = "2097573390f1"
down_revision = "fc32e7db4493"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=900000;")
    with op.batch_alter_table("invoice_references", schema=None) as batch_op:
        batch_op.add_column(sa.Column("created_on", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_consolidated", sa.Boolean(), server_default="f", nullable=False
            )
        )
        batch_op.create_index(
            batch_op.f("ix_invoice_references_is_consolidated"),
            ["is_consolidated"],
            unique=False,
        )
    op.execute(
        "update invoice_references set is_consolidated = 't' where invoice_number like '%-C'"
    )


def downgrade():
    with op.batch_alter_table("invoice_references", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invoice_references_is_consolidated"))
        batch_op.drop_column("is_consolidated")
        batch_op.drop_column("created_on")
