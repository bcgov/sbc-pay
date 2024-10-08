"""gl_updated_status

Revision ID: bb5b5cab004b
Revises: 7231303dabdf
Create Date: 2020-08-13 16:50:08.972605

"""

from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "bb5b5cab004b"
down_revision = "7231303dabdf"
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table(
        "invoice_status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table,
        [{"code": "GL_UPDATED", "description": "Revenue account updated"}],
    )


def downgrade():
    op.execute("DELETE FROM invoice_status_code WHERE code = 'GL_UPDATED';")
