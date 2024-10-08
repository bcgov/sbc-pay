"""add expense authority email list

Revision ID: f921d5e32835
Revises: 5aa18f715e3e
Create Date: 2024-07-12 12:19:17.094866

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f921d5e32835"
down_revision = "5aa18f715e3e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eft_refund_email_list",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(25), nullable=True),
        sa.Column("last_name", sa.String(25), nullable=True),
        sa.Column("email", sa.String(25), nullable=False),
    )


def downgrade():
    op.drop_table("eft_refund_email_list")
