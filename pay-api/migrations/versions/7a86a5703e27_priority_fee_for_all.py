"""priority_fee_for_all

Revision ID: 7a86a5703e27
Revises: 5cdd1c1d355e
Create Date: 2020-02-26 14:18:10.817049

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7a86a5703e27"
down_revision = "5cdd1c1d355e"
branch_labels = None
depends_on = None


def upgrade():
    # update all fee schedule to have priority filing and future effective filing except for free filings
    op.execute(
        "update fee_schedule set priority_fee_code='PRI01' where fee_code != 'EN107';"
    )


def downgrade():
    op.execute(
        "update fee_schedule set priority_fee_code=null where filing_type_code not in ('BCRSC', 'BCAMR', 'BCAMH', 'BCAMV', 'BCRSF', 'BCRSL', 'BCRSX', 'CRCTN');"
    )
