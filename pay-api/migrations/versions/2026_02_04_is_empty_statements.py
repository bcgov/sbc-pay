"""Add is_empty flag to statements.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_empty", sa.Boolean(), nullable=False, server_default="1"
            )
        )

    # Backfill: set is_empty = false for statements that have statement_invoices
    op.execute(
        """
        UPDATE statements s
        SET is_empty = false
        WHERE EXISTS (
            SELECT 1 FROM statement_invoices si WHERE si.statement_id = s.id
        )
        """
    )


def downgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_column("is_empty")
