"""Add GST tax rate data also rename column enable_gst to gst_added

Revision ID: 42c1a9619006
Revises: 38045c22fe00
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
down_revision = 'eb14e6b27e34'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"""
        INSERT INTO tax_rates (tax_type, rate, start_date, effective_end_date, description, updated_by, updated_name)
        VALUES ('{TAX_CLASSIFICATION_GST}', 0.05, '{datetime.now(tz=timezone.utc).isoformat()}', NULL, 'Canadian Goods and Services Tax', 'migration', 'System Migration')
    """)
    op.alter_column('fee_schedules', 'enable_gst', new_column_name='gst_added')
    op.execute("UPDATE payment_line_items SET service_fees_gst = 0 WHERE service_fees_gst IS NULL")
    op.execute("UPDATE payment_line_items SET statutory_fees_gst = 0 WHERE statutory_fees_gst IS NULL")
    
    op.alter_column('payment_line_items', 'service_fees_gst',
                    nullable=False,
                    server_default='0')
    op.alter_column('payment_line_items', 'statutory_fees_gst',
                    nullable=False,
                    server_default='0')
    

def downgrade():
    op.alter_column('payment_line_items', 'service_fees_gst',
                    nullable=True,
                    server_default=None)
    op.alter_column('payment_line_items', 'statutory_fees_gst',
                    nullable=True,
                    server_default=None)
    
    op.alter_column('fee_schedules', 'gst_added', new_column_name='enable_gst')
    op.execute(f"""
        DELETE FROM tax_rates 
        WHERE tax_type = '{TAX_CLASSIFICATION_GST}' 
        AND rate = 0.05 
        AND updated_by = 'migration'
    """)
