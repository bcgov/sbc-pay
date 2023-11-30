"""Add in a sequence column to the ejv_invoice_links table

Revision ID: 49eaec3210e0
Revises: 598bbfce4dad
Create Date: 2023-11-30 10:38:00.644319

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '49eaec3210e0'
down_revision = '598bbfce4dad'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ejv_invoice_links', sa.Column('sequence', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_ejv_invoice_links_sequence'), 'ejv_invoice_links', ['sequence'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ejv_invoice_links_sequence'), table_name='ejv_invoice_links')
    op.drop_column('ejv_invoice_links', 'sequence')
