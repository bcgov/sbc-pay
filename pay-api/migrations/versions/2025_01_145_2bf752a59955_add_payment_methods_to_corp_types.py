"""empty message

Revision ID: 2bf752a59955
Revises: a8c7fe27f821
Create Date: 2025-01-14 10:25:25.521509

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '2bf752a59955'
down_revision = 'a8c7fe27f821'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    UPDATE corp_types 
    SET payment_methods = ARRAY['PAD', 'DIRECT_PAY', 'INTERNAL']
    WHERE product = 'STRR'
    """)

def downgrade():
    pass
