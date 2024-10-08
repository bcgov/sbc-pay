"""Revision to add in no fee service fees.

Revision ID: f4a1388844ed
Revises: d2d9864164d1
Create Date: 2023-03-07 13:22:28.195608

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4a1388844ed"
down_revision = "d2d9864164d1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "insert into fee_codes (code, amount) values ('TRF04', 0.00) ON CONFLICT DO NOTHING;"
    )
    op.add_column("credits", sa.Column("details", sa.String(length=200), nullable=True))
    op.add_column("credits", sa.Column("created_on", sa.DateTime(), nullable=True))


def downgrade():
    op.execute("delete from fee_codes where code = 'TRF04';")
    op.drop_column("credits", "details")
    op.drop_column("credits", "created_on")
