"""payment_table_master_inserts

Revision ID: 0420566ac811
Revises: 4a4dfbf28f22
Create Date: 2019-05-23 09:15:00.002181

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "0420566ac811"
down_revision = "4a4dfbf28f22"
branch_labels = None
depends_on = None


def upgrade():
    payment_method_table = table(
        "payment_method", column("code", String), column("description", String)
    )
    payment_system_table = table(
        "payment_system", column("code", String), column("description", String)
    )
    status_code_table = table(
        "status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(payment_method_table, [{"code": "CC", "description": "Credit Card"}])
    op.bulk_insert(
        payment_system_table, [{"code": "PAYBC", "description": "Pay BC System"}]
    )
    op.bulk_insert(
        status_code_table,
        [
            {"code": "DRAFT", "description": "Draft"},
            {"code": "IN_PROGRESS", "description": "In Progress"},
            {"code": "CREATED", "description": "Created"},
            {"code": "COMPLETED", "description": "Completed"},
            {"code": "PARTIAL", "description": "Partial"},
            {"code": "FAILED", "description": "Failed"},
            {"code": "REFUNDED", "description": "Refunded"},
            {"code": "CANCELLED", "description": "Cancelled"},
        ],
    )


def downgrade():
    pass
