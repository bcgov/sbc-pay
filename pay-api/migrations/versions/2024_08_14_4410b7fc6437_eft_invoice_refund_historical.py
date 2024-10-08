"""Invoice refund support for eft_short_names_historical

Revision ID: 4410b7fc6437
Revises: 5cb9c5f5896c
Create Date: 2024-08-14 10:42:13.484178

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = "4410b7fc6437"
down_revision = "5cb9c5f5896c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("eft_short_names_historical", schema=None) as batch_op:
        batch_op.add_column(sa.Column("invoice_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_eft_short_names_historical_invoice_id"),
            ["invoice_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "eft_short_names_historical_invoice_id_fkey",
            "invoices",
            ["invoice_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("eft_short_names_historical", schema=None) as batch_op:
        batch_op.drop_constraint(
            "eft_short_names_historical_invoice_id_fkey", type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_eft_short_names_historical_invoice_id"))
        batch_op.drop_column("invoice_id")
