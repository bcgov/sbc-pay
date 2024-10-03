"""Enable partner disbursements for certain corp types.

Revision ID: 56c4542db0d7
Revises: aae01971bd53
Create Date: 2024-09-17 06:26:15.691631

"""
from alembic import op
import sqlalchemy as sa
from pay_api.utils.enums import DisbursementStatus, EJVLinkType

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '56c4542db0d7'
down_revision = 'aae01971bd53'
branch_labels = None
depends_on = None


def upgrade():
  op.execute("update corp_types set has_partner_disbursements = 't' where code in ('CSO', 'VS')")
  op.execute(f"""insert into partner_disbursements (amount, created_on, partner_code, is_reversal, status_code, target_id, target_type)
            select (i.total - i.service_fees) as amount, now() as created_on, i.corp_type_code as partner_code, 'f' as is_reversal,
                    '{DisbursementStatus.WAITING_FOR_RECEIPT.value}' as status_code, i.id as target_id, '{EJVLinkType.INVOICE.value}' as target_type from invoices i where invoice_status_code in ('APPROVED', 'PAID')
                                                                                                                    and corp_type_code in ('CSO','VS') and payment_method_code = 'EFT' 
            """)

def downgrade():
  op.execute("update corp_types set has_partner_disbursements = 'f' where code in ('CSO', 'VS')")
