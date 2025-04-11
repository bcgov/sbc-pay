"""Add partial refund column to payment methods

Revision ID: 706b28ee3b37
Revises: f6e2fd9710b7
Create Date: 2025-04-11 10:40:01.404822

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import PaymentMethod


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '706b28ee3b37'
down_revision = 'f6e2fd9710b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payment_methods', sa.Column('partial_refund', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(f"""
        UPDATE payment_methods
        SET partial_refund = true
        WHERE code IN ('{PaymentMethod.PAD.value}', '{PaymentMethod.DIRECT_PAY.value}', '{PaymentMethod.ONLINE_BANKING.value}')
    """)


def downgrade():
    op.drop_column('payment_methods', 'partial_refund')
