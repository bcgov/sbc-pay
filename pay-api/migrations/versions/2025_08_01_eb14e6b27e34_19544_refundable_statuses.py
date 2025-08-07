"""Add refundable statuses to payment methods

Revision ID: eb14e6b27e34
Revises: b927265cf3a1
Create Date: 2025-08-01 08:48:56.118139

"""
from alembic import op
import sqlalchemy as sa

revision = 'eb14e6b27e34'
down_revision = '38045c22fe00'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(f"""UPDATE payment_methods SET partial_refund = true WHERE code = 'EFT'""")

    with op.batch_alter_table('payment_methods', schema=None) as batch_op:
        batch_op.add_column(sa.Column('full_refund_statuses', sa.ARRAY(sa.String()), nullable=True))

    op.execute("""
               UPDATE payment_methods
               SET full_refund_statuses =
                       CASE code
                           WHEN 'CC' THEN ARRAY['PAID']
                           WHEN 'DIRECT_PAY' THEN ARRAY['PAID']
                           WHEN 'DRAWDOWN' THEN ARRAY['PAID']
                           WHEN 'EFT' THEN ARRAY['APPROVED', 'PAID']
                           WHEN 'EJV' THEN ARRAY['APPROVED', 'PAID']
                           WHEN 'INTERNAL' THEN ARRAY['PAID']
                           WHEN 'ONLINE_BANKING' THEN ARRAY['PAID']
                           WHEN 'PAD' THEN ARRAY['APPROVED', 'PAID']
                           END
               WHERE code IS NOT NULL
               """)

def downgrade():
    op.execute(f"""UPDATE payment_methods SET partial_refund = false WHERE code = 'EFT'""")
    with op.batch_alter_table('payment_methods', schema=None) as batch_op:
        batch_op.drop_column('full_refund_statuses')
