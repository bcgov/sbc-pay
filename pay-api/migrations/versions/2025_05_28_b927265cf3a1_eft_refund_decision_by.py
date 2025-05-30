"""28627 - EFT Approver / Decliner update to use decision_by as updated_by can be overridden in other processes such
as queue or job logic

Revision ID: b927265cf3a1
Revises: afccd441770e
Create Date: 2025-05-28 14:01:48.597195

"""
from alembic import op
import sqlalchemy as sa

revision = 'b927265cf3a1'
down_revision = 'afccd441770e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('decision_by', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('eft_refunds', schema=None) as batch_op:
        batch_op.drop_column('decision_by')
