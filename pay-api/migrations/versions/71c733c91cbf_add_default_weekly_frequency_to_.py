"""add default weekly frequency to statement settings

Revision ID: 71c733c91cbf
Revises: bcb296e7f6f4
Create Date: 2020-08-20 18:05:57.263571

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
from pay_api.utils.enums import StatementFrequency


revision = "71c733c91cbf"
down_revision = "bcb296e7f6f4"
branch_labels = None
depends_on = None


def upgrade():
    default_frequency = StatementFrequency.default_frequency().value
    sql = (
        f"INSERT INTO statement_settings (frequency, payment_account_id, from_date) "
        f"SELECT '{default_frequency}', account_id, CURRENT_DATE FROM bcol_payment_account;"
    )
    op.execute(sql)


def downgrade():
    op.execute("DELETE FROM statement_settings")
