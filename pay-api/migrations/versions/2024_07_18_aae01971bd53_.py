"""Add in has_partner_disbursements column to corp_types, easier for querying

Revision ID: aae01971bd53
Revises: fb59bf68146d
Create Date: 2024-07-18 10:51:20.058891

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'aae01971bd53'
down_revision = 'fb59bf68146d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('corp_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_partner_disbursements', sa.Boolean(), nullable=True))

def downgrade():
    with op.batch_alter_table('corp_types', schema=None) as batch_op:
        batch_op.drop_column('has_partner_disbursements')
