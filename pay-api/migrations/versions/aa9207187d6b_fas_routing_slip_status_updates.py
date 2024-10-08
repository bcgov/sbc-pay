"""fas_routing_slip_status_updates

Revision ID: aa9207187d6b
Revises: b336780735dc
Create Date: 2021-12-10 10:28:11.033487

"""

from alembic import op
import sqlalchemy as sa

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "aa9207187d6b"
down_revision = "b336780735dc"
branch_labels = None
depends_on = None


def upgrade():
    rs_status_table = table(
        "routing_slip_status_codes",
        column("code", sa.String),
        column("description", sa.String),
    )
    op.bulk_insert(
        rs_status_table,
        [
            {"code": "WRITE_OFF", "description": "Write Off"},
            {"code": "REFUND_REJECTED", "description": "Refund Rejected"},
        ],
    )
    op.execute(
        "delete from routing_slip_status_codes where code in ('BOUNCED', 'REFUND');"
    )


def downgrade():
    op.execute(
        "delete from routing_slip_status_codes where code in ('WRITE_OFF', 'REFUND_REJECTED');"
    )
