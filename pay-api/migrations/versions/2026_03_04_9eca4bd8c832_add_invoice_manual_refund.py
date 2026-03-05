"""
Add MANUAL_REFUNDED invoice status code.
Revision ID: 9eca4bd8c832
Revises: 1b96dd80e686
Create Date: 2026-03-04 15:43:41.258631

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '9eca4bd8c832'
down_revision = '1b96dd80e686'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO invoice_status_codes (code, description) "
        "VALUES ('MANUAL_REFUNDED', 'Manual Refunded') "
        "ON CONFLICT DO NOTHING"
    )


def downgrade():
    op.execute("DELETE FROM invoice_status_codes WHERE code = 'MANUAL_REFUNDED'")
