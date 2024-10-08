"""refunds

Revision ID: 086e16326076
Revises: 2d025cbefda8
Create Date: 2020-11-03 12:33:45.092189

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "086e16326076"
down_revision = "2d025cbefda8"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("requested_date", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=250), nullable=True),
        sa.Column("requested_by", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoice.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    error_code_table = table(
        "error_code",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    status_code_table = table(
        "payment_status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(status_code_table, [{"code": "REFUNDED", "description": "Refunded"}])

    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "INVALID_REQUEST",
                "title": "Invalid Request",
                "detail": "Unable to process invalid request",
            }
        ],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("refunds")
    op.execute("delete from payment_status_code where code='REFUNDED'")
    op.execute("delete from error_code where code='INVALID_REQUEST'")
    # ### end Alembic commands ###
