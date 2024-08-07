"""Move EFT invoices from created to APPROVED.

Revision ID: d197b43e25dc
Revises: e64c153e63ae
Create Date: 2024-08-07 11:49:14.975144

"""
from alembic import op
from pay_api.utils.enums import InvoiceStatus

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'd197b43e25dc'
down_revision = 'e64c153e63ae'
branch_labels = None
depends_on = None

def upgrade():
    op.execute(f"update invoices set invoice_status_code = '{InvoiceStatus.APPROVED.value}' where invoice_status_code = '{InvoiceStatus.CREATED.value}' and payment_method_code = 'EFT'")

def downgrade():
    op.execute(f"update invoices set invoice_status_code = '{InvoiceStatus.CREATED.value}' where invoice_status_code = '{InvoiceStatus.APPROVED.value}' and payment_method_code = 'EFT'")
