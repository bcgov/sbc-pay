"""24454 - EFT File column clean up

Revision ID: 8bd139bbb602
Revises: 474917a13bd4
Create Date: 2024-11-19 21:20:17.080264

"""
from alembic import op
import sqlalchemy as sa

revision = '8bd139bbb602'
down_revision = '474917a13bd4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_files', schema=None) as batch_op:
        batch_op.drop_column('total_deposit_cents')
        batch_op.drop_column('number_of_details')


def downgrade():
    with op.batch_alter_table('eft_files', schema=None) as batch_op:
        batch_op.add_column(sa.Column('number_of_details', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('total_deposit_cents', sa.BIGINT(), autoincrement=False, nullable=True))
