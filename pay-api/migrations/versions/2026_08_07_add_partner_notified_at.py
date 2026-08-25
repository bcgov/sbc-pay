"""add_partner_notified_at_to_invoice_payment_links

Revision ID: d9e14b2c7a03
Revises: a17c3f9b1e4d
Create Date: 2026-08-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d9e14b2c7a03"
down_revision = "a17c3f9b1e4d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoice_payment_links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("partner_notified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.execute("ALTER TABLE invoice_payment_links DROP COLUMN IF EXISTS partner_notified_at")
