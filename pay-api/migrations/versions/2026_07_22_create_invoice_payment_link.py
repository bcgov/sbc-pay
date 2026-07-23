"""create_invoice_payment_link

Revision ID: a17c3f9b1e4d
Revises: 968a2e428d4c
Create Date: 2026-07-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a17c3f9b1e4d"
down_revision = "968a2e428d4c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_payment_links",
        sa.Column("token", sa.String(length=32), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_ipl_invoice_id", "invoice_payment_links", ["invoice_id"], unique=False,
    )


def downgrade():
    op.drop_index("idx_ipl_invoice_id", table_name="invoice_payment_links")
    op.drop_table("invoice_payment_links")
