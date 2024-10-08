"""added invoice approved status 

Revision ID: a66de2954e70
Revises: 073b9f59b447
Create Date: 2021-02-26 11:19:49.408284

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "a66de2954e70"
down_revision = "073b9f59b447"
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table(
        "invoice_status_codes", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table, [{"code": "APPROVED", "description": "PAD Invoice Approved"}]
    )


def downgrade():
    op.execute('DELETE FROM invoice_status_code WHERE code = "APPROVED";')
