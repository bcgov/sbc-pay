"""More indexes for performance

Revision ID: 2ccbd2aad2dc
Revises: f218f09ea2d2
Create Date: 2022-05-02 16:54:13.727083

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2ccbd2aad2dc"
down_revision = "f218f09ea2d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_payments_payment_account_id"),
        table_name="payments",
        columns=["payment_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_routing_slips_payment_account_id"),
        table_name="routing_slips",
        columns=["payment_account_id"],
        unique=False,
    )
    pass


def downgrade():
    op.drop_index(op.f("ix_payments_payment_account_id"), table_name="payments")
    op.drop_index(
        op.f("ix_routing_slips_payment_account_id"), table_name="routing_slips"
    )
    pass
