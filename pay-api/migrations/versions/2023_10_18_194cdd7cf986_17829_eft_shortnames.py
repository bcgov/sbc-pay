"""17829-eft-shortnames

Revision ID: 194cdd7cf986
Revises: 456234145e5e
Create Date: 2023-10-18 08:23:04.207463

"""

from alembic import op
import sqlalchemy as sa

from pay_api import db

# revision identifiers, used by Alembic.
revision = "194cdd7cf986"
down_revision = "456234145e5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eft_short_names",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("short_name", sa.String(), nullable=False, unique=True),
        sa.Column("auth_account_id", sa.String(length=50), nullable=True),
        sa.Column("created_on", sa.DateTime(), nullable=False),
    )

    op.create_index(
        op.f("ix_eft_short_names_auth_account_id"),
        "eft_short_names",
        ["auth_account_id"],
        unique=False,
    )


def downgrade():
    op.drop_table("eft_short_names")
