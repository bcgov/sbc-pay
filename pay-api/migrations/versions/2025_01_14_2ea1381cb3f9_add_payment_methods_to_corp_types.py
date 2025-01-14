"""Adding in payment methods for STRR

Revision ID: 2ea1381cb3f9
Revises: 695a899f8a25
Create Date: 2025-01-14 07:24:19.485823

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '2ea1381cb3f9'
down_revision = '695a899f8a25'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    UPDATE corp_types 
    SET payment_methods = ARRAY['PAD', 'DIRECT_PAY', 'EFT', 'EJV', 'ONLINE_BANKING', 'DRAWDOWN', 'INTERNAL']
    WHERE product = 'STRR'
    """)


def downgrade():
    pass
