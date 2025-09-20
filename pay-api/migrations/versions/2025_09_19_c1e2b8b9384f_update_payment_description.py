"""Update payment method descriptions for DRAWDOWN and INTERNAL

Revision ID: c1e2b8b9384f
Revises: b313916b778a
Create Date: 2025-09-19 16:29:06.658059

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'c1e2b8b9384f'
down_revision = 'b313916b778a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE payment_methods SET description = 'BC Online' WHERE code = 'DRAWDOWN'")
    op.execute("UPDATE payment_methods SET description = 'Routing Slip' WHERE code = 'INTERNAL'")


def downgrade():
    op.execute("UPDATE payment_methods SET description = 'Drawdown Payment' WHERE code = 'DRAWDOWN'")
    op.execute("UPDATE payment_methods SET description = 'Staff Payment' WHERE code = 'INTERNAL'")
