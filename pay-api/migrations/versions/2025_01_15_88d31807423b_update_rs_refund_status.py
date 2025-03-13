"""Update: Queue Missing update for RoutingSlipRefundStatus to PROCESSED when status is REFUND_PROCESSED

Revision ID: 88d31807423b
Revises: 2bf752a59955
Create Date: 2025-01-15 15:33:56.268441

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import ChequeRefundStatus, RoutingSlipStatus


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '88d31807423b'
down_revision = '2bf752a59955'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"""
        UPDATE routing_slips
        SET refund_status = '{ChequeRefundStatus.PROCESSED.value}'
        WHERE status = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)


def downgrade():
    pass
