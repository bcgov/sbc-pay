"""Rename enable_gst to gst_added in fee_schedules

Revision ID: b5245a85a4e6
Revises: 38045c22fe00
Create Date: 2025-08-01 09:08:45.591823

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'b5245a85a4e6'
down_revision = '38045c22fe00'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('fee_schedules', 'enable_gst', new_column_name='gst_added')


def downgrade():
    op.alter_column('fee_schedules', 'gst_added', new_column_name='enable_gst')
