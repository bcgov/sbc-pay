"""Remove gst column from payment_line_items table.

Revision ID: 18c691c0edd2
Revises: 42c1a9619006
Create Date: 2025-08-13 11:24:55.323461

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '18c691c0edd2'
down_revision = '42c1a9619006'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payment_line_items', schema=None) as batch_op:
        batch_op.drop_column('gst')


def downgrade():
    with op.batch_alter_table('payment_line_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gst', sa.NUMERIC(precision=19, scale=2), autoincrement=False, nullable=False,
                                      server_default='0'))
