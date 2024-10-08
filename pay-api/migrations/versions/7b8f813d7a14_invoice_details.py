"""invoice_details

Revision ID: 7b8f813d7a14
Revises: 7649a31bfe39
Create Date: 2021-05-05 17:12:28.523093

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7b8f813d7a14"
down_revision = "7649a31bfe39"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "invoices",
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("invoices", "details")
    # ### end Alembic commands ###
