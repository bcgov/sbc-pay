"""Add in is_credit column to refunds_partial table.

Revision ID: 94ca57d30196
Revises: d83a66f9ccb6
Create Date: 2025-07-24 12:37:07.619991

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '94ca57d30196'
down_revision = 'd83a66f9ccb6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_credit', sa.Boolean(), nullable=False, server_default="f"))

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_credit', sa.Boolean(), autoincrement=False, nullable=False, server_default="f"))

    op.execute("""
        UPDATE refunds_partial 
        SET is_credit = CASE 
            WHEN invoice_id IN (
                SELECT id FROM invoices 
                WHERE payment_method_code IN ('PAD', 'ONLINE_BANKING', 'INTERNAL', 'EFT')
            ) THEN TRUE
            ELSE FALSE
        END
    """)
    
    op.execute("""
        UPDATE refunds_partial_history 
        SET is_credit = CASE 
            WHEN invoice_id IN (
                SELECT id FROM invoices 
                WHERE payment_method_code IN ('PAD', 'ONLINE_BANKING', 'INTERNAL', 'EFT')
            ) THEN TRUE
            ELSE FALSE
        END
    """)


def downgrade():
    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.drop_column('is_credit')

    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.drop_column('is_credit')
