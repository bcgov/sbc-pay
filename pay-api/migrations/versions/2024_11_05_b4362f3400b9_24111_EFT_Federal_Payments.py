"""24111 - EFT Federal Payments Support

Revision ID: b4362f3400b9
Revises: 5fa0fea09841
Create Date: 2024-11-05 08:07:56.879869

"""
from alembic import op
import sqlalchemy as sa

revision = 'b4362f3400b9'
down_revision = '5fa0fea09841'
branch_labels = None
depends_on = None


def upgrade():
    # EFT Short name sequence used to generate short name for supported TDI17 transactions that do not have a short name
    # e.g. FEDERAL PAYMENT CANADA
    op.execute(
        sa.schema.CreateSequence(
            sa.Sequence("eft_short_name_seq", data_type=sa.Integer)
        )
    )

    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_generated', sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    op.execute("DROP SEQUENCE eft_short_name_seq")

    with op.batch_alter_table('eft_short_names', schema=None) as batch_op:
        batch_op.drop_column('is_generated')
