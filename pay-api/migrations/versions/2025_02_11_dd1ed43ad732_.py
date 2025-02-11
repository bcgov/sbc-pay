"""Update BTR Product

Revision ID: dd1ed43ad732
Revises: 3103082f36d5
Create Date: 2025-02-11 05:50:13.255651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'dd1ed43ad732'
down_revision = '3103082f36d5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    UPDATE corp_types 
    SET product = 'BTR'
    WHERE code = 'BTR'
    """)
    pass


def downgrade():
    pass
