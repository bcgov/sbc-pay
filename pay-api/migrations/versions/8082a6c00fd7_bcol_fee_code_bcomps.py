"""bcol_fee_code_bcomps

Revision ID: 8082a6c00fd7
Revises: 1ad89abae65d
Create Date: 2020-06-01 13:48:57.429958

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "8082a6c00fd7"
down_revision = "1ad89abae65d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("update corp_type set bcol_fee_code='BCOMVC01' where code in ('BC')")
    op.execute(
        "update payment_status_code set description='Completed' where code = 'COMPLETED' "
    )


def downgrade():
    op.execute("update corp_type set bcol_fee_code='' where code in ('BC')")
    op.execute(
        "update payment_status_code set description='Paid' where code = 'COMPLETED' "
    )
