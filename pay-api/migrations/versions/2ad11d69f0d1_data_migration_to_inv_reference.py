"""data_migration_to_inv_reference

Revision ID: 2ad11d69f0d1
Revises: e0cacec26024
Create Date: 2019-11-13 16:51:02.118022

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "2ad11d69f0d1"
down_revision = "e0cacec26024"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO "
        "invoice_reference  "
        "(invoice_id, invoice_number, reference_number, status_code) "
        "SELECT "
        "id, invoice_number, reference_number, invoice_status_code "
        "FROM invoice;"
    )


def downgrade():
    op.execute("DELETE FROM invoice_reference")
