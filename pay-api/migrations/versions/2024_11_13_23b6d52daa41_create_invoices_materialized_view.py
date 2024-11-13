"""create transactions_materialized_view

Revision ID: 23b6d52daa41
Revises: 0f02d5964a63
Create Date: 2024-11-13 09:31:35.075717

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '23b6d52daa41'
down_revision = '0f02d5964a63'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("set statement_timeout=900000;")
    op.execute('''
        CREATE MATERIALIZED VIEW transactions_materialized_view AS
        SELECT 
            fee_schedules.fee_schedule_id,
            fee_schedules.filing_type_code,
            payment_line_items.id AS line_item_id,
            payment_line_items.description,
            payment_line_items.gst,
            payment_line_items.pst,
            payment_accounts.id AS payment_account_id,
            payment_accounts.auth_account_id,
            payment_accounts.name AS payment_account_name,
            payment_accounts.billable,
            invoice_references.id AS invoice_reference_id,
            invoice_references.invoice_number,
            invoice_references.reference_number,
            invoice_references.status_code AS invoice_reference_status_code,
            invoices.id AS invoice_id,
            invoices.invoice_status_code,
            invoices.payment_method_code,
            invoices.corp_type_code,
            invoices.disbursement_date,
            invoices.disbursement_reversal_date,
            invoices.created_on,
            invoices.business_identifier,
            invoices.total,
            invoices.paid,
            invoices.payment_date,
            invoices.overdue_date,
            invoices.refund_date,
            invoices.refund,
            invoices.filing_id,
            invoices.folio_number,
            invoices.bcol_account,
            invoices.service_fees,
            invoices.details,
            invoices.created_by,
            invoices.created_name
        FROM 
            invoices
        LEFT OUTER JOIN payment_accounts ON invoices.payment_account_id = payment_accounts.id
        LEFT OUTER JOIN payment_line_items ON payment_line_items.invoice_id = invoices.id
        LEFT OUTER JOIN fee_schedules ON fee_schedules.fee_schedule_id = payment_line_items.fee_schedule_id
        LEFT OUTER JOIN invoice_references ON invoice_references.invoice_id = invoices.id
        ORDER BY invoices.id DESC;
    ''')

    op.execute('''
        CREATE INDEX idx_transactions_materialized_view_auth_account_id_invoice_id_desc
        ON transactions_materialized_view (auth_account_id, invoice_id DESC);
    ''')


def downgrade():
    op.execute('''
        DROP INDEX IF EXISTS idx_transactions_materialized_view_auth_account_id_invoice_id_desc;
    ''')

    op.execute('''
        DROP MATERIALIZED VIEW IF EXISTS transactions_materialized_view;
    ''')
