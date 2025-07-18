"""applied credits implementation

Revision ID: d83a66f9ccb6
Revises: a7b9c2d4e6f8
Create Date: 2025-07-14 15:29:03.866023

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'd83a66f9ccb6'
down_revision = 'a7b9c2d4e6f8'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('cfs_credit_invoices', 'applied_credits')
    op.execute("ALTER TABLE applied_credits RENAME CONSTRAINT cfs_credit_invoices_account_id_fkey TO applied_credits_account_id_fkey")
    op.execute("ALTER TABLE applied_credits RENAME CONSTRAINT cfs_credit_invoices_credit_id_fkey TO applied_credits_credit_id_fkey")
    op.execute("ALTER TABLE applied_credits DROP CONSTRAINT IF EXISTS cfs_credit_invoices_application_id_key")
    op.execute("DROP INDEX IF EXISTS ix_cfs_credit_invoices_application_id")
    op.create_index('ix_applied_credits_application_id', 'applied_credits', ['application_id'])
    op.execute("ALTER INDEX IF EXISTS ix_cfs_credit_invoices_cfs_account RENAME TO ix_applied_credits_cfs_account")
    op.execute("ALTER INDEX IF EXISTS ix_cfs_credit_invoices_cfs_identifier RENAME TO ix_applied_credits_cfs_identifier")
    op.execute("ALTER INDEX IF EXISTS ix_cfs_credit_invoices_credit_id RENAME TO ix_applied_credits_credit_id")
    op.add_column('applied_credits', sa.Column('invoice_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_applied_credits_invoice_id_invoices', 'applied_credits', 'invoices', ['invoice_id'], ['id'])
    op.create_index('ix_applied_credits_invoice_id', 'applied_credits', ['invoice_id'], unique=False)
    op.add_column('credits', sa.Column('created_invoice_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_credits_created_invoice_id_invoices',
        'credits', 'invoices',
        ['created_invoice_id'], ['id']
    )
    op.create_index('ix_credits_created_invoice_id', 'credits', ['created_invoice_id'], unique=False)


def downgrade():
    op.drop_index('ix_credits_created_invoice_id', table_name='credits')
    op.drop_constraint('fk_credits_created_invoice_id_invoices', 'credits', type_='foreignkey')
    op.drop_column('credits', 'created_invoice_id')
    op.drop_index('ix_applied_credits_invoice_id', table_name='applied_credits')
    op.drop_constraint('fk_applied_credits_invoice_id_invoices', 'applied_credits', type_='foreignkey')
    op.drop_column('applied_credits', 'invoice_id')
    op.execute("DROP INDEX IF EXISTS ix_applied_credits_application_id")
    op.create_index('ix_cfs_credit_invoices_application_id', 'cfs_credit_invoices', ['application_id'], unique=True)
    op.execute("ALTER INDEX IF EXISTS ix_applied_credits_cfs_account RENAME TO ix_cfs_credit_invoices_cfs_account")
    op.execute("ALTER INDEX IF EXISTS ix_applied_credits_cfs_identifier RENAME TO ix_cfs_credit_invoices_cfs_identifier")
    op.execute("ALTER INDEX IF EXISTS ix_applied_credits_credit_id RENAME TO ix_cfs_credit_invoices_credit_id")
    op.execute("ALTER TABLE cfs_credit_invoices RENAME CONSTRAINT applied_credits_account_id_fkey TO cfs_credit_invoices_account_id_fkey")
    op.execute("ALTER TABLE cfs_credit_invoices RENAME CONSTRAINT applied_credits_credit_id_fkey TO cfs_credit_invoices_credit_id_fkey")
    op.rename_table('applied_credits', 'cfs_credit_invoices')
