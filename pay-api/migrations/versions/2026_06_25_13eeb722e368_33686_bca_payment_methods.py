"""33686-bca_payment_methods

Revision ID: 13eeb722e368
Revises: e1f2a3b4c5d6
Create Date: 2026-06-25 09:05:44.685719

"""
from alembic import op
import sqlalchemy as sa


revision = '13eeb722e368'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
               UPDATE corp_types
               SET payment_methods = ARRAY['PAD', 'DIRECT_PAY', 'EFT', 'EJV', 'DRAWDOWN', 'INTERNAL']
               WHERE product = 'BCA'
               """)


def downgrade():
    op.execute("""
               UPDATE corp_types
               SET payment_methods = ARRAY['PAD', 'EFT', 'EJV', 'DRAWDOWN', 'INTERNAL']
               WHERE product = 'BCA'
               """)
