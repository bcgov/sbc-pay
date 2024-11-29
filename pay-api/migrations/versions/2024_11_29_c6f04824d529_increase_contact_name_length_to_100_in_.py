"""Increase contact_name length to 100 in routing_slips

Revision ID: c6f04824d529
Revises: 8bd139bbb602
Create Date: 2024-11-29 10:12:25.626056

"""
from alembic import op
import sqlalchemy as sa

revision = 'c6f04824d529'
down_revision = '8bd139bbb602'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.alter_column('contact_name', 
                              existing_type=sa.String(length=50),
                              type_=sa.String(length=100),
                              existing_nullable=True)


def downgrade():
    with op.batch_alter_table('routing_slips', schema=None) as batch_op:
        batch_op.alter_column('contact_name', 
                              existing_type=sa.String(length=100),
                              type_=sa.String(length=50),
                              existing_nullable=True)
