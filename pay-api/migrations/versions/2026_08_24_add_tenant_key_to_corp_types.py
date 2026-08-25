"""add_tenant_key_to_corp_types_and_invoice_payment_links

Revision ID: b8f2d4c9e1a3
Revises: d9e14b2c7a03
Create Date: 2026-08-24 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b8f2d4c9e1a3"
down_revision = "d9e14b2c7a03"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("corp_types", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_key", sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f("ix_corp_types_tenant_key"), ["tenant_key"], unique=False)

    with op.batch_alter_table("invoice_payment_links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_key", sa.String(length=50), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_invoice_payment_links_tenant_key"), ["tenant_key"], unique=False
        )


def downgrade():
    with op.batch_alter_table("invoice_payment_links", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invoice_payment_links_tenant_key"))
    op.execute("ALTER TABLE invoice_payment_links DROP COLUMN IF EXISTS tenant_key")

    with op.batch_alter_table("corp_types", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_corp_types_tenant_key"))
    op.execute("ALTER TABLE corp_types DROP COLUMN IF EXISTS tenant_key")
