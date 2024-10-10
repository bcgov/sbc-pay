"""Small fix for status code

Revision ID: ed487561aeeb
Revises: d1996caed682
Create Date: 2024-10-10 11:36:29.069307

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import DisbursementStatus


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'ed487561aeeb'
down_revision = 'd1996caed682'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        f"update partner_disbursements set status_code = '{DisbursementStatus.WAITING_FOR_JOB.value}' where status_code = 'WAITING_FOR_RECEIPT'"
    )


def downgrade():
    pass
