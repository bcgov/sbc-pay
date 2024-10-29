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

    # 1. Insert the new status into the `routing_slip_status_codes` table
    op.execute(f"""
        INSERT INTO routing_slip_status_codes (code, description)
        VALUES ('{RoutingSlipStatus.REFUND_PROCESSED.value}', 'Refund Processed')
        ON CONFLICT (code) DO NOTHING;
    """)

    # 2. Update the status reference in the `routing_slips` table
    op.execute(f"""
        UPDATE routing_slips
        SET status = '{RoutingSlipStatus.REFUND_PROCESSED.value}'
        WHERE status = 'REFUND_COMPLETED';
    """)

    # 3. Delete the old status `REFUND_COMPLETED`
    op.execute("""
        DELETE FROM routing_slip_status_codes
        WHERE code = 'REFUND_COMPLETED';
    """)


def downgrade():
    op.execute("""
        INSERT INTO routing_slip_status_codes (code, description)
        VALUES ('REFUND_COMPLETED', 'Refund Complete')
        ON CONFLICT (code) DO NOTHING;
    """)

    op.execute(f"""
        UPDATE routing_slips
        SET status = 'REFUND_COMPLETED'
        WHERE status = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)

    op.execute(f"""
        DELETE FROM routing_slip_status_codes
        WHERE code = '{RoutingSlipStatus.REFUND_PROCESSED.value}';
    """)

    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.drop_column('refund_status')
