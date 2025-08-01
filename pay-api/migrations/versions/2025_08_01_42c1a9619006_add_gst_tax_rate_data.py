"""Add GST tax rate data

Revision ID: 42c1a9619006
Revises: b5245a85a4e6
Create Date: 2025-08-01 09:29:53.939705

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

from pay_api.utils.constants import TAX_CLASSIFICATION_GST


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '42c1a9619006'
down_revision = 'b5245a85a4e6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"""
        INSERT INTO tax_rates (tax_type, rate, start_date, effective_end_date, description, updated_by, updated_name)
        VALUES ('{TAX_CLASSIFICATION_GST}', 0.05, '{datetime.now(tz=timezone.utc).isoformat()}', NULL, 'Canadian Goods and Services Tax', 'migration', 'System Migration')
    """)


def downgrade():
    op.execute(f"""
        DELETE FROM tax_rates 
        WHERE tax_type = '{TAX_CLASSIFICATION_GST}' 
        AND rate = 0.05 
        AND updated_by = 'migration'
    """)
