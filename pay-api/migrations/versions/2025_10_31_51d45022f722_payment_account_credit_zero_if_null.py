"""Set payment_accounts credits to zero if they are null.

Revision ID: 51d45022f722
Revises: c1e2b8b9384f
Create Date: 2025-10-31 11:31:21.653563

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '51d45022f722'
down_revision = 'c1e2b8b9384f'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    UPDATE payment_accounts 
    SET pad_credit = 0
    WHERE pad_credit is null;
    """)

    op.execute("""
    UPDATE payment_accounts 
    SET eft_credit = 0
    WHERE eft_credit is null;
    """)

    op.execute("""
    UPDATE payment_accounts 
    SET ob_credit = 0
    WHERE ob_credit is null;
    """)



def downgrade():
  pass
   