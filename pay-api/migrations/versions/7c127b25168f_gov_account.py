"""gov_account

Revision ID: 7c127b25168f
Revises: a66de2954e70
Create Date: 2021-03-11 12:25:33.138896

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "7c127b25168f"
down_revision = "a66de2954e70"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    payment_system_table = table(
        "payment_systems", column("code", String), column("description", String)
    )
    op.bulk_insert(
        payment_system_table, [{"code": "CGI", "description": "CAS Generic Interface"}]
    )
    op.add_column(
        "distribution_codes", sa.Column("account_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_distribution_codes_account_id"),
        "distribution_codes",
        ["account_id"],
        unique=False,
    )
    op.create_foreign_key(
        "distribution_codes_payment_accounts_fk",
        "distribution_codes",
        "payment_accounts",
        ["account_id"],
        ["id"],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "distribution_codes_payment_accounts_fk",
        "distribution_codes",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_distribution_codes_account_id"), table_name="distribution_codes"
    )
    op.drop_column("distribution_codes", "account_id")
    op.execute("delete from payment_systems where code='CGI'")

    # ### end Alembic commands ###
