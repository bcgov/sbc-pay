"""Drop deprecated gst_added column from fee_schedules and fee_schedules_history.

Revision ID: e1f2a3b4c5d6
Revises: d22c3e446ce8
Create Date: 2026-06-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd22c3e446ce8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("fee_schedules", schema=None) as batch_op:
        batch_op.drop_column("gst_added")

    with op.batch_alter_table("fee_schedules_history", schema=None) as batch_op:
        batch_op.drop_column("gst_added")


def downgrade():
    with op.batch_alter_table("fee_schedules_history", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "gst_added",
                sa.Boolean(),
                autoincrement=False,
                nullable=True,
                comment="Flag to indicate if GST is added for this fee schedule",
            )
        )

    with op.batch_alter_table("fee_schedules", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "gst_added",
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
                comment="Flag to indicate if GST is added for this fee schedule",
            )
        )
