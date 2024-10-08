"""payment_failed_status

Revision ID: b05d371ad030
Revises: b7443d501d98
Create Date: 2020-11-23 11:56:48.721202

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "b05d371ad030"
down_revision = "b7443d501d98"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "payment", sa.Column("cons_inv_number", sa.String(length=50), nullable=True)
    )
    op.create_index(
        op.f("ix_payment_cons_inv_number"), "payment", ["cons_inv_number"], unique=False
    )

    status_code_table = table(
        "payment_status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(status_code_table, [{"code": "FAILED", "description": "Failed"}])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_payment_cons_inv_number"), table_name="payment")
    op.drop_column("payment", "cons_inv_number")

    op.execute("delete from payment_status_code where code='FAILED'")

    # ### end Alembic commands ###
