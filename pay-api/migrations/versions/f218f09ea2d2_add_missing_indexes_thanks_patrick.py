"""add missing indexes (thanks Patrick)

Revision ID: f218f09ea2d2
Revises: 059abb33d3c3
Create Date: 2022-05-02 06:48:12.608456

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f218f09ea2d2"
down_revision = "059abb33d3c3"
branch_labels = None
depends_on = None


def upgrade():
    # Remove hand made indexes.
    op.execute("DROP INDEX IF EXISTS ix_invoices_routing_slip")
    op.execute("DROP INDEX IF EXISTS ix_payment_line_items_invoice_id")
    op.execute("DROP INDEX IF EXISTS ix_receipts_invoice_id")

    op.create_index(
        op.f("ix_invoices_routing_slip"), "invoices", ["routing_slip"], unique=False
    )
    op.create_index(
        op.f("ix_payment_line_items_invoice_id"),
        "payment_line_items",
        ["invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_receipts_invoice_id"), "receipts", ["invoice_id"], unique=False
    )
    pass


def downgrade():
    op.drop_index(op.f("ix_invoices_routing_slip"), table_name="invoices")
    op.drop_index(
        op.f("ix_payment_line_items_invoice_id"), table_name="payment_line_items"
    )
    op.drop_index(op.f("ix_receipts_invoice_id"), table_name="receipts")
    pass
