"""added pay system reason codes

Revision ID: 1803b51e5689
Revises: ebee125e6877
Create Date: 2021-02-18 07:10:07.192436

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "1803b51e5689"
down_revision = "ebee125e6877"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payment_transactions",
        sa.Column("pay_system_reason_code", sa.String(length=2000), nullable=True),
    )


def downgrade():
    op.drop_column("payment_transactions", "pay_system_reason_code")
