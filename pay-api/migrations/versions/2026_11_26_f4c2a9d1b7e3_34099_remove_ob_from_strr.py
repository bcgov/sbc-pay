"""34099-remove_ob_from_strr

Revision ID: f4c2a9d1b7e3
Revises: e3b8c1d4f7a2
Create Date: 2026-11-26 10:00:00.000000

"""
from alembic import op


revision = 'f4c2a9d1b7e3'
down_revision = 'e3b8c1d4f7a2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
               UPDATE corp_types
               SET payment_methods = array_remove(payment_methods, 'ONLINE_BANKING')
               WHERE product = 'STRR'
               """)


def downgrade():
    op.execute("""
               UPDATE corp_types
               SET payment_methods = ARRAY['PAD', 'DIRECT_PAY', 'EFT', 'EJV', 'ONLINE_BANKING', 'INTERNAL']
               WHERE product = 'STRR'
               """)
