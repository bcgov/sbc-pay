"""add_refund_allowed_to_corp_types

Revision ID: 968a2e428d4c
Revises: 13eeb722e368
Create Date: 2026-07-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "968a2e428d4c"
down_revision = "13eeb722e368"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("corp_types", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("refund_allowed", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    with op.batch_alter_table("corp_types_history", schema=None) as batch_op:
        batch_op.add_column(sa.Column("refund_allowed", sa.Boolean(), nullable=True))

    op.execute("UPDATE corp_types SET refund_allowed = false WHERE code = 'BCA'")


def downgrade():
    with op.batch_alter_table("corp_types_history", schema=None) as batch_op:
        batch_op.drop_column("refund_allowed")

    with op.batch_alter_table("corp_types", schema=None) as batch_op:
        batch_op.drop_column("refund_allowed")
