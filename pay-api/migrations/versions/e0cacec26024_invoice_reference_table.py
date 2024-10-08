"""invoice_reference_table

Revision ID: e0cacec26024
Revises: 861324fa9b37
Create Date: 2019-11-13 16:50:05.381555

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e0cacec26024"
down_revision = "861324fa9b37"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "invoice_reference",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=50), nullable=True),
        sa.Column("reference_number", sa.String(length=50), nullable=True),
        sa.Column("status_code", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoice.id"],
        ),
        sa.ForeignKeyConstraint(
            ["status_code"],
            ["status_code.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invoice_reference_invoice_number"),
        "invoice_reference",
        ["invoice_number"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_invoice_reference_invoice_number"), table_name="invoice_reference"
    )
    op.drop_table("invoice_reference")
    # ### end Alembic commands ###
