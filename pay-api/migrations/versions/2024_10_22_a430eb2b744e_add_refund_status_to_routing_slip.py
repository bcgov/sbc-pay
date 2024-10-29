"""add refund status to routing slip

Revision ID: a430eb2b744e
Revises: 59db97e9432e
Create Date: 2024-10-22 14:56:56.311470

"""
from alembic import op
import sqlalchemy as sa
from pay_api.utils.enums import RoutingSlipStatus


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'a430eb2b744e'
down_revision = '59db97e9432e'
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa

def upgrade():
    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refund_status', sa.String(length=50), nullable=True))

    op.execute(f"""
        UPDATE routing_slip_status_codes
        SET code = '{RoutingSlipStatus.REFUND_PROCESSED.value}', description = 'Refund Processed'
        WHERE code = 'REFUND_COMPLETED';
    """)

    # Update the records in routing_slips where status is 'REFUND_COMPLETED'
    op.execute(f"""
        UPDATE routing_slips
        SET status = '{RoutingSlipStatus.REFUND_PROCESSED.value}'
        WHERE status = 'REFUND_COMPLETED';
    """)


def downgrade():
    op.execute(f"""
        UPDATE routing_slips
        SET status = 'REFUND_COMPLETED'
        WHERE status = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)

    op.execute(f"""
        UPDATE routing_slip_status_codes
        SET code = 'REFUND_COMPLETED', description = 'Refund Complete'
        WHERE code = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)

    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.drop_column('refund_status')
