"""empty message

Revision ID: 7231303dabdf
Revises: 39a97401040c
Create Date: 2020-08-04 15:10:59.301538

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7231303dabdf"
down_revision = "39a97401040c"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "payment_line_item",
        "fee_distribution_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.add_column(
        "payment_transaction",
        sa.Column("pay_response_url", sa.String(length=500), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("payment_transaction", "pay_response_url")
    op.alter_column(
        "payment_line_item",
        "fee_distribution_id",
        existing_type=sa.INTEGER(),
        nullable=True,
    )
    # ### end Alembic commands ###
