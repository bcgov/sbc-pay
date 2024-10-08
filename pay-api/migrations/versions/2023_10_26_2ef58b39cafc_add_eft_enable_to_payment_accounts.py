"""18099-eft allowed flag

Revision ID: 2ef58b39cafc
Revises: 194cdd7cf986
Create Date: 2023-10-26 13:31:50.959562

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2ef58b39cafc"
down_revision = "194cdd7cf986"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=20000;")
    op.add_column(
        "payment_accounts",
        sa.Column("eft_enable", sa.Boolean(), nullable=False, server_default="f"),
    )
    op.add_column(
        "payment_accounts_version",
        sa.Column("eft_enable", sa.Boolean(), nullable=False, server_default="f"),
    )


def downgrade():
    op.execute("set statement_timeout=20000;")
    op.drop_column("payment_accounts", "eft_enable")
    op.drop_column("payment_accounts_version", "eft_enable")
