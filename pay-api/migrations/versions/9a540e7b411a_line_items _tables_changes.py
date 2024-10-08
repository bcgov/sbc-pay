"""add a UPDATED status code and status column to payment line items table

Revision ID: 9a540e7b411a
Revises: 2ffe44097a0e
Create Date: 2019-06-10 09:55:45.248157

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "9a540e7b411a"
down_revision = "2ffe44097a0e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payment", sa.Column("paid", sa.Float(), autoincrement=False, nullable=True)
    )

    op.add_column(
        "payment_line_item",
        sa.Column("line_item_status_code", sa.String(length=10), nullable=True),
    )

    line_item = table("payment_line_item", column("line_item_status_code"))
    op.execute(line_item.update().values(line_item_status_code="CREATED"))
    op.alter_column("payment_line_item", "line_item_status_code", nullable=False)

    op.create_foreign_key(
        "fk_line_item_status",
        "payment_line_item",
        "status_code",
        ["line_item_status_code"],
        ["code"],
    )

    status_code_table = table(
        "status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(status_code_table, [{"code": "UPDATED", "description": "Updated"}])


def downgrade():
    op.drop_column("payment", "paid")
    op.drop_column("payment_line_item", "line_item_status_code")
