"""Add CHARGEBACK invoice status.

Revision ID: 1b96dd80e686
Revises: b2c3d4e5f6a7
Create Date: 2026-02-26 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1b96dd80e686"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "insert into invoice_status_codes (code, description) values ('CHARGEBACK', 'Credit Card Chargeback')"
    )


def downgrade():
    op.execute("delete from invoice_status_codes where code = 'CHARGEBACK'")
