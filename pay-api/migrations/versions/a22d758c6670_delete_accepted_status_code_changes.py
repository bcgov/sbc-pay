"""delete_accepted_status_code_changes

Revision ID: a22d758c6670
Revises: 79ba9960e1dc
Create Date: 2019-11-20 08:43:02.119625

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "a22d758c6670"
down_revision = "79ba9960e1dc"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "invoice",
        "invoice_status_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "invoice_reference",
        "status_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "payment",
        "payment_status_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "payment_line_item",
        "line_item_status_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "payment_line_item",
        "line_item_status_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )

    status_code_table = table(
        "status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table,
        [{"code": "DELETE_ACCEPTED", "description": "Accepted to Delete"}],
    )


def downgrade():
    op.alter_column(
        "invoice",
        "invoice_status_code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "invoice_reference",
        "status_code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "payment",
        "payment_status_code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "payment_line_item",
        "line_item_status_code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "payment_line_item",
        "line_item_status_code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
