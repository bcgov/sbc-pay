"""empty message

Revision ID: 6468cb5380db
Revises: 7aff4af4be85
Create Date: 2022-06-23 15:24:18.914367

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6468cb5380db'
down_revision = '7aff4af4be85'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE VIEW RPT_INVOICES_PLI as
        select
            pa.auth_account_id,
            pa.name,
            pa.payment_method,
            created_on at time zone 'utc' at time zone 'america/vancouver' as created_pst,
            updated_on at time zone 'utc' at time zone 'america/vancouver' as updated_pst,
            i.id,
            invoice_number,
            pli.total
        from
            invoices i
        join invoice_references ir on
            i.id = ir.invoice_id
        join payment_accounts pa on
            pa.id = i.payment_account_id
        join payment_line_items pli on
            pli.invoice_id = i.id;
    ''')
    op.execute('''CREATE VIEW RPT_INVOICES as
        select
            pa.auth_account_id,
            i.id as invoice_id,
            invoice_number,
            filing_id,
            pa.bcol_account,
            created_on at time zone 'utc' at time zone 'America/Vancouver' as created_on,
            created_by,
            created_name,
            invoice_status_code,
            total,
            paid,
            payment_method_code
        from
            invoices i
        left join payment_accounts pa on
            pa.id = i.payment_account_id
        left join invoice_references ir on
            i.id = ir.invoice_id
    ''')

def downgrade():
    op.execute('DROP VIEW RPT_INVOICES_PLI')
    op.execute('DROP VIEW RPT_INVOICES')
