""" Add in column for payment_method.

Revision ID: f6990cf5ddf1
Revises: 0672573574f6
Create Date: 2024-07-08 10:31:00.670490

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f6990cf5ddf1"
down_revision = "0672573574f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cfs_accounts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("payment_method", sa.String(length=15), nullable=True)
        )
        batch_op.create_foreign_key(
            None, "payment_methods", ["payment_method"], ["code"]
        )

    with op.batch_alter_table("cfs_accounts_history", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "payment_method",
                sa.String(length=15),
                autoincrement=False,
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            None, "payment_methods", ["payment_method"], ["code"]
        )


def downgrade():
    with op.batch_alter_table("cfs_accounts_history", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_column("payment_method")

    with op.batch_alter_table("cfs_accounts", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_column("payment_method")
