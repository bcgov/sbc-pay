"""add processing to all rs refund requests

Revision ID: c76e8338de35
Revises: a430eb2b744e
Create Date: 2024-10-28 14:30:39.918097

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import ChequeRefundStatus, RoutingSlipStatus


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'c76e8338de35'
down_revision = 'a430eb2b744e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"""
        UPDATE routing_slips
        SET refund_status = '{ChequeRefundStatus.PROCESSING.value}'
        WHERE status  in ('{RoutingSlipStatus.REFUND_REQUESTED.value}', '{RoutingSlipStatus.REFUND_AUTHORIZED.value}', '{RoutingSlipStatus.REFUND_UPLOADED.value}');
    """)
    op.execute(f"""
        UPDATE routing_slips
        SET refund_status = '{ChequeRefundStatus.PROCESSED.value}'
        WHERE status = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)


def downgrade():
    op.execute(f"""
        UPDATE routing_slips
        SET refund_status = Null
        WHERE status in ('{RoutingSlipStatus.REFUND_REQUESTED.value}', '{RoutingSlipStatus.REFUND_AUTHORIZED.value}', '{RoutingSlipStatus.REFUND_UPLOADED.value}');
    """)
    op.execute(f"""
        UPDATE routing_slips
        SET refund_status = Null
        WHERE status = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)
