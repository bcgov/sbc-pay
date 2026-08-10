"""express_checkout_schema

Creates the `invoice_payment_links` table and adds the two express-checkout flags
to `corp_types` in one migration — same feature, land together.

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
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_ipl_invoice_id", "invoice_payment_links", ["invoice_id"], unique=False,
    )

    with op.batch_alter_table("corp_types", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_express_checkout_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("payment_link_ttl_days", sa.Integer(), nullable=True))

    with op.batch_alter_table("corp_types_history", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_express_checkout_enabled", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("payment_link_ttl_days", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("corp_types_history", schema=None) as batch_op:
        batch_op.drop_column("payment_link_ttl_days")
        batch_op.drop_column("is_express_checkout_enabled")

    with op.batch_alter_table("corp_types", schema=None) as batch_op:
        batch_op.drop_column("payment_link_ttl_days")
        batch_op.drop_column("is_express_checkout_enabled")

    op.drop_index("idx_ipl_invoice_id", table_name="invoice_payment_links")
    op.drop_table("invoice_payment_links")
