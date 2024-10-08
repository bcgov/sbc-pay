"""adding_filing_id_to_invoice

Revision ID: 861324fa9b37
Revises: e6eb14b9d50e
Create Date: 2019-11-04 15:41:02.521095

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "861324fa9b37"
down_revision = "e6eb14b9d50e"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "invoice", sa.Column("filing_id", sa.String(length=50), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("invoice", "filing_id")
    # ### end Alembic commands ###
