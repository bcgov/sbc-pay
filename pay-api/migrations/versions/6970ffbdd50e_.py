"""Add in index for invoices.payment_account_id.

Revision ID: 6970ffbdd50e
Revises: 6468cb5380db
Create Date: 2022-07-13 19:24:22.375268

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6970ffbdd50e"
down_revision = "6468cb5380db"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(
        op.f("ix_invoices_payment_account_id"),
        "invoices",
        ["payment_account_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_invoices_payment_account_id"), table_name="invoices")
    # ### end Alembic commands ###
