"""EFT Refunds additional columns

Revision ID: 29f59e6f147b
Revises: 67407611eec8
Create Date: 2024-09-19 16:09:53.120704

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.

revision = "29f59e6f147b"
down_revision = "67407611eec8"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("eft_refunds", schema=None) as batch_op:
        batch_op.add_column(sa.Column("decline_reason", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("created_by", sa.String(length=100), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("eft_refunds", schema=None) as batch_op:
        batch_op.drop_column("created_by")
        batch_op.drop_column("decline_reason")
