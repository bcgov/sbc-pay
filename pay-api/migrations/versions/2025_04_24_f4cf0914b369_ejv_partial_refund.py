"""Add partial refund for EJV

Revision ID: f4cf0914b369
Revises: 706b28ee3b37
Create Date: 2025-04-24 16:33:41.120358

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import PaymentMethod


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'f4cf0914b369'
down_revision = '706b28ee3b37'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"""
        UPDATE payment_methods
        SET partial_refund = true
        WHERE code IN ('{PaymentMethod.EJV.value}')
    """)


def downgrade():
    op.execute(f"""
        UPDATE payment_methods
        SET partial_refund = false
        WHERE code IN ('{PaymentMethod.EJV.value}')
    """)

