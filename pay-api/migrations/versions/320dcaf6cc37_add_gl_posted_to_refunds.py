"""add gl_posted to refunds, mainly for backend processing and audit.

Revision ID: 320dcaf6cc37
Revises: c3a87b8ea180
Create Date: 2022-08-16 07:09:35.899316

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "320dcaf6cc37"
down_revision = "c3a87b8ea180"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("refunds", sa.Column("gl_posted", sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("refunds", "gl_posted")
    # ### end Alembic commands ###
