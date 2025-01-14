"""Modifying payment methods for STRR

Revision ID: a8c7fe27f821
Revises: 2ea1381cb3f9
Create Date: 2025-01-14 09:14:32.108914

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'a8c7fe27f821'
down_revision = '2ea1381cb3f9'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    UPDATE corp_types 
    SET payment_methods = ARRAY['PAD', 'DIRECT_PAY', 'EFT', 'EJV', 'ONLINE_BANKING', 'INTERNAL']
    WHERE product = 'STRR'
    """)


def downgrade():
    pass
