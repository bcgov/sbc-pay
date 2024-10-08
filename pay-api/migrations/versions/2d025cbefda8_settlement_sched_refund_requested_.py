"""settlement_sched_refund_requested_invoice_status

Revision ID: 2d025cbefda8
Revises: 320f9f89eb68
Create Date: 2020-10-30 09:06:18.397112

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "2d025cbefda8"
down_revision = "320f9f89eb68"
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table(
        "invoice_status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table,
        [
            {"code": "REFUND_REQUESTED", "description": "Refund Requested"},
            {"code": "SETTLEMENT_SCHED", "description": "Settlement Scheduled"},
        ],
    )


def downgrade():
    op.execute(
        "delete from invoice_status_code where code in ('REFUND_REQUESTED', 'SETTLEMENT_SCHED')"
    )
