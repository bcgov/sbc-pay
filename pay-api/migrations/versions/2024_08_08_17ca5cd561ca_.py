"""Create indexes to optimize amount owing.

Revision ID: 17ca5cd561ca
Revises: d197b43e25dc
Create Date: 2024-08-08 11:31:56.857656

"""

from alembic import op

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = "17ca5cd561ca"
down_revision = "d197b43e25dc"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=900000;")
    with op.batch_alter_table("invoices", schema=None) as batch_op:
        # existing adhoc on PROD
        op.execute("DROP INDEX IF EXISTS invoices_invoice_status_code_idx;")
        batch_op.create_index(
            batch_op.f("ix_invoices_invoice_status_code"),
            ["invoice_status_code"],
            unique=False,
        )

    with op.batch_alter_table("statement_invoices", schema=None) as batch_op:
        # existing adhoc on PROD
        op.execute("DROP INDEX IF EXISTS statement_invoices_invoice_id_idx;")
        batch_op.create_index(
            batch_op.f("ix_statement_invoices_invoice_id"), ["invoice_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("statement_invoices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_statement_invoices_invoice_id"))

    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invoices_invoice_status_code"))
