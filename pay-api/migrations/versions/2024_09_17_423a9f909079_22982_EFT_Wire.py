"""22982 - Add EFT Short name type for Wire

Revision ID: 423a9f909079
Revises: 1fadb0e78d8c
Create Date: 2024-09-17 08:18:05.315144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.

revision = '423a9f909079'
down_revision = '1fadb0e78d8c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type', sa.String(), nullable=True))

    with op.batch_alter_table('eft_short_names_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type', sa.String(), autoincrement=False, nullable=True))

    op.execute("update eft_short_names set type = 'EFT' where type is null")
    op.execute("update eft_short_names_history set type = 'EFT' where type is null")

    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.alter_column('type', nullable=False)

    with op.batch_alter_table('eft_short_names_history', schema=None) as batch_op:
        batch_op.alter_column('type', nullable=False)


def downgrade():
    with op.batch_alter_table('eft_short_names_history', schema=None) as batch_op:
        batch_op.drop_column('type')

    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.drop_column('type')
