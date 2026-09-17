"""add_email_and_return_url_to_invoice_payment_links

Revision ID: c7d2e5f8a9b1
Revises: b8f2d4c9e1a3
Create Date: 2026-09-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c7d2e5f8a9b1"
down_revision = "b8f2d4c9e1a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoice_payment_links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(254), nullable=True))
        batch_op.add_column(sa.Column("return_url", sa.String(2048), nullable=True))


def downgrade():
    op.execute("ALTER TABLE invoice_payment_links DROP COLUMN IF EXISTS email")
    op.execute("ALTER TABLE invoice_payment_links DROP COLUMN IF EXISTS return_url")
