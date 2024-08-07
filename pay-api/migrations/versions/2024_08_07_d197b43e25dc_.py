"""Move EFT invoices from created to APPROVED.

Revision ID: d197b43e25dc
Revises: 1d5b66ef7f81
Create Date: 2024-08-07 11:49:14.975144

"""
from alembic import op

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'd197b43e25dc'
down_revision = '1d5b66ef7f81'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("update invoices set invoice_status_code = 'APPROVED' where invoice_status_code = 'CREATED' and payment_method_code = 'EFT'")

def downgrade():
    op.execute("update invoices set invoice_status_code = 'CREATED' where invoice_status_code = 'APPROVED' and payment_method_code = 'EFT'")
