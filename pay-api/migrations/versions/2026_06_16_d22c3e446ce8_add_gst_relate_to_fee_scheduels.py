"""Add statutory_fees_gst_added and service_fees_gst_added columns to fee_schedules table.
Revision ID: d22c3e446ce8
Revises: 9b1c4d7e8f90
Create Date: 2026-06-16 10:08:37.927339

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'd22c3e446ce8'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("fee_schedules", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "statutory_fees_gst_added",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="Flag to indicate if GST is added for statutory fees for this fee schedule",
            )
        )
        batch_op.add_column(
            sa.Column(
                "service_fees_gst_added",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="Flag to indicate if GST is added for service fees for this fee schedule",
            )
        )

    op.execute(
        """
        UPDATE fee_schedules
        SET statutory_fees_gst_added = COALESCE(gst_added, FALSE),
            service_fees_gst_added = COALESCE(gst_added, FALSE)
        """
    )

    with op.batch_alter_table("fee_schedules_history", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "statutory_fees_gst_added",
                sa.Boolean(),
                autoincrement=False,
                nullable=True,
                comment="Flag to indicate if GST is added for statutory fees for this fee schedule",
            )
        )
        batch_op.add_column(
            sa.Column(
                "service_fees_gst_added",
                sa.Boolean(),
                autoincrement=False,
                nullable=True,
                comment="Flag to indicate if GST is added for service fees for this fee schedule",
            )
        )

    op.execute(
        """
        UPDATE fee_schedules_history
        SET statutory_fees_gst_added = COALESCE(gst_added, FALSE),
            service_fees_gst_added = COALESCE(gst_added, FALSE)
        """
    )


def downgrade():
    with op.batch_alter_table("fee_schedules_history", schema=None) as batch_op:
        batch_op.drop_column("service_fees_gst_added")
        batch_op.drop_column("statutory_fees_gst_added")

    with op.batch_alter_table("fee_schedules", schema=None) as batch_op:
        batch_op.drop_column("service_fees_gst_added")
        batch_op.drop_column("statutory_fees_gst_added")
