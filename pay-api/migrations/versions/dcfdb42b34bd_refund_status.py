"""refund_status

Revision ID: dcfdb42b34bd
Revises: f74980cff974
Create Date: 2021-10-13 13:49:03.440224

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = 'dcfdb42b34bd'
down_revision = 'f74980cff974'
branch_labels = None
depends_on = None


def upgrade():
    invoice_status_codes = table(
        "invoice_status_codes", column("code", String), column("description", String)
    )
    op.bulk_insert(
        invoice_status_codes, [
            {"code": "REFUNDED", "description": "Refunded"}
        ]
    )


def downgrade():
    op.execute("delete from invoice_status_codes where code='REFUNDED';")
