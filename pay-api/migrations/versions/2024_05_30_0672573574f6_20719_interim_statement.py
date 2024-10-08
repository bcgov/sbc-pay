"""20719 Add interim statement flag

Revision ID: 0672573574f6
Revises: 4b3bd37727a5
Create Date: 2024-05-30 08:26:03.121991

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0672573574f6"
down_revision = "4b3bd37727a5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_interim_statement", sa.Boolean(), nullable=False, server_default="0"
            )
        )


def downgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_column("is_interim_statement")
