"""Small fix that changes routing slip statuses next time this migration hits prod.
We had to deploy main to prod to fix another issue.

Revision ID: 5fa0fea09841
Revises: c76e8338de35
Create Date: 2024-10-31 15:40:04.636234

"""
from alembic import op
import sqlalchemy as sa
from pay_api.utils.enums import RoutingSlipStatus


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '5fa0fea09841'
down_revision = 'c76e8338de35'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"update routing_slips set status = '{RoutingSlipStatus.REFUND_PROCESSED.value}' where status = 'REFUND_COMPLETED';")
    op.execute("delete from routing_slip_status_codes where code = 'REFUND_COMPLETED';")

def downgrade():
    op.execute("INSERT INTO routing_slip_status_codes (code, description) VALUES ('REFUND_COMPLETED', 'Refund Complete');")
    op.execute(f"update routing_slips set status = 'REFUND_COMPLETED' where status = '{RoutingSlipStatus.REFUND_PROCESSED.value}';")
