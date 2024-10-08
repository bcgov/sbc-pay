"""refund_error_messages

Revision ID: 9543cbcb8b79
Revises: f841ac43e15e
Create Date: 2021-08-23 13:21:30.339589

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "9543cbcb8b79"
down_revision = "f841ac43e15e"
branch_labels = None
depends_on = None


def upgrade():
    error_code_table = table(
        "error_codes",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    op.execute(
        "delete from error_codes where code in ('ROUTING_SLIP_REFUND', 'NO_FEE_REFUND') "
    )
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "ROUTING_SLIP_REFUND",
                "title": "Routing slip refund is not allowed.",
                "detail": "Routing slip refund is not allowed. You will not receive an automatic refund. Please call 1-877-370-1033 to request a refund.",
            },
            {
                "code": "NO_FEE_REFUND",
                "title": "No fees to refund.",
                "detail": "No fees to refund. Please contact BC Registry staff at 1-877-370-1033 if you require assistance.",
            },
        ],
    )


def downgrade():
    op.execute(
        "delete from error_codes where code in ('ROUTING_SLIP_REFUND', 'NO_FEE_REFUND') "
    )
