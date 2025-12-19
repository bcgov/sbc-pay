"""Add pad_credit to statement.

Revision ID: 1206aded914a
Revises: 76b874c82ad6
Create Date: 2025-12-17 16:17:16.372380

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '1206aded914a'
down_revision = '76b874c82ad6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('statements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pad_credit', sa.Numeric(precision=19, scale=2), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('eft_credit', sa.Numeric(precision=19, scale=2), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('ob_credit', sa.Numeric(precision=19, scale=2), autoincrement=False, nullable=True))


def downgrade():
    with op.batch_alter_table('statements', schema=None) as batch_op:
        batch_op.drop_column('ob_credit')
        batch_op.drop_column('eft_credit')
        batch_op.drop_column('pad_credit')
