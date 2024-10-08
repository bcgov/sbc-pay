"""refund statuses

Revision ID: cfa9e9f222f5
Revises: 4cb0dc8e0013
Create Date: 2021-10-19 11:54:58.725048

"""

from alembic import op
import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "cfa9e9f222f5"
down_revision = "4cb0dc8e0013"
branch_labels = None
depends_on = None


def upgrade():
    disbursement_status_codes = table(
        "disbursement_status_codes",
        column("code", String),
        column("description", String),
    )
    op.bulk_insert(
        disbursement_status_codes, [{"code": "REVERSED", "description": "Reversed"}]
    )


def downgrade():
    op.execute("delete from disbursement_status_codes where code='REVERSED';")
