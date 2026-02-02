"""Add performance indexes for statement generation.

Revision ID: a1b2c3d4e5f6
Revises: f52120aa9993
Create Date: 2026-02-02 10:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'a1b2c3d4e5f6'
down_revision = 'f52120aa9993'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_statement_invoices_statement_invoice
        ON statement_invoices (statement_id, invoice_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_statements_account_freq_dates
        ON statements (payment_account_id, frequency, from_date, to_date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_invoices_payment_account_created_on
        ON invoices (payment_account_id, created_on)
    """)


def downgrade():
    op.execute('DROP INDEX IF EXISTS ix_invoices_payment_account_created_on')
    op.execute('DROP INDEX IF EXISTS ix_statements_account_freq_dates')
    op.execute('DROP INDEX IF EXISTS ix_statement_invoices_statement_invoice')
