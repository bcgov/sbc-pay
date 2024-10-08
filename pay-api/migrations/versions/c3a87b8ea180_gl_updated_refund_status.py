"""Add in new invoice status for refunds.

Revision ID: c3a87b8ea180
Revises: cc2dcab68760
Create Date: 2022-08-15 15:22:38.982600

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "c3a87b8ea180"
down_revision = "cc2dcab68760"
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table(
        "invoice_status_codes", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table,
        [
            {
                "code": "GL_UPDATED_REFUND",
                "description": "Revenue account updated - Refund",
            }
        ],
    )


def downgrade():
    op.execute("DELETE FROM invoice_status_code WHERE code = 'GL_UPDATED_REFUND';")
