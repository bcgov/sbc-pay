"""30294 - EFT Credit memo handling

Revision ID: b313916b778a
Revises: 18c691c0edd2
Create Date: 2025-08-20 09:30:02.990837

"""
from alembic import op
import sqlalchemy as sa

revision = 'b313916b778a'
down_revision = '18c691c0edd2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('eft_credit', sa.Numeric(precision=19, scale=2), nullable=True))

    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('eft_credit', sa.Numeric(precision=19, scale=2), autoincrement=False, nullable=True))


def downgrade():
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.drop_column('eft_credit')

    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.drop_column('eft_credit')
