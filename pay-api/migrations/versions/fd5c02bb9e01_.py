"""Migration to set cas_version_suffix to 1 for existing records

Revision ID: fd5c02bb9e01
Revises: f497d603602e
Create Date: 2022-12-15 13:12:09.563178

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fd5c02bb9e01"
down_revision = "f497d603602e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "update routing_slips set cas_version_suffix = 1 where cas_version_suffix is null"
    )
    pass
