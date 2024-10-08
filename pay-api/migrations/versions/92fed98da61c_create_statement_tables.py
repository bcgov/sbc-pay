"""create statement tables

Revision ID: 92fed98da61c
Revises: 7231303dabdf
Create Date: 2020-08-13 06:39:51.780897

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "92fed98da61c"
down_revision = "7231303dabdf"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "statement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("frequency", sa.String(length=50), nullable=True),
        sa.Column("payment_account_id", sa.Integer(), nullable=True),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["payment_account_id"],
            ["payment_account.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_statement_payment_account_id"),
        "statement",
        ["payment_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_statement_frequency"), "statement", ["frequency"], unique=False
    )
    op.create_index(op.f("ix_statement_status"), "statement", ["status"], unique=False)
    op.create_table(
        "statement_invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("inovice_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["inovice_id"],
            ["invoice.id"],
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["statement.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_statement_invoices_statement_id"),
        "statement_invoices",
        ["statement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_statement_invoices_status"),
        "statement_invoices",
        ["status"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_statement_invoices_status"), table_name="statement_invoices")
    op.drop_index(
        op.f("ix_statement_invoices_statement_id"), table_name="statement_invoices"
    )
    op.drop_table("statement_invoices")
    op.drop_index(op.f("ix_statement_status"), table_name="statement")
    op.drop_index(op.f("ix_statement_frequency"), table_name="statement")
    op.drop_index(op.f("ix_statement_payment_account_id"), table_name="statement")
    op.drop_table("statement")
    # ### end Alembic commands ###
