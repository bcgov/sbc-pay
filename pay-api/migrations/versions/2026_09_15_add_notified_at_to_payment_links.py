"""add_notified_at_to_invoice_payment_links

Revision ID: d9f4a7e2c8b6
Revises: c7d2e5f8a9b1
Create Date: 2026-09-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d9f4a7e2c8b6"
down_revision = "c7d2e5f8a9b1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoice_payment_links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.execute("ALTER TABLE invoice_payment_links DROP COLUMN IF EXISTS notified_at")
