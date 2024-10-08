"""Add better tracking to how much EFT credit is spent as it is possible an invoice is paid through multiple
EFT Transactions. A status is also added to allow for EFT credits to be applied later via a job.

Revision ID: 4b3bd37727a5
Revises: 29867cf1bd9e
Create Date: 2024-05-07 08:32:12.812898

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4b3bd37727a5"
down_revision = "29867cf1bd9e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("eft_credit_invoice_links", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("status_code", sa.String(length=25), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_eft_credit_invoice_links_status_code"),
            ["status_code"],
            unique=False,
        )

    op.execute(text(f"UPDATE eft_credit_invoice_links " f"SET status_code = 'PENDING'"))


def downgrade():
    with op.batch_alter_table("eft_credit_invoice_links", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_eft_credit_invoice_links_status_code"))
        batch_op.drop_column("status_code")
        batch_op.drop_column("amount")
