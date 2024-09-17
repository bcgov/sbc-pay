"""Enable partner disbursements for certain corp types.

Revision ID: 56c4542db0d7
Revises: aae01971bd53
Create Date: 2024-09-17 06:26:15.691631

"""
from alembic import op
import sqlalchemy as sa


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

def downgrade():
  op.execute("update corp_types set has_partner_disbursements = 'f' where code in ('CSO', 'VS')")
