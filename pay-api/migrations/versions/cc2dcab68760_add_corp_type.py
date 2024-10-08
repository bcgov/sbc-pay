""" Add corp_types to views.

Revision ID: cc2dcab68760
Revises: 59fc9d74101f
Create Date: 2022-07-29 11:33:20.861072

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "cc2dcab68760"
down_revision = "59fc9d74101f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """CREATE OR REPLACE VIEW RPT_INVOICES_PLI as
        select
            created_on at time zone 'utc' at time zone 'america/vancouver' as created_pst,
            updated_on at time zone 'utc' at time zone 'america/vancouver' as updated_pst,
            pa.auth_account_id,
            pa.name,
            i.id as invoice_id,
            payment_method_code,
            invoice_number,
            routing_slip,
            pli.total as pli_total,
            i.total as invoice_total,
            i.paid as invoice_paid,
            pli.service_fees as pli_service_fees,
            i.service_fees,
            i.corp_type_code
        from
            invoices i
        left join invoice_references ir on
            i.id = ir.invoice_id
        left join payment_accounts pa on
            pa.id = i.payment_account_id
        left join payment_line_items pli on
            pli.invoice_id = i.id;
    """
    )
    op.execute(
        """CREATE OR REPLACE VIEW RPT_INVOICES as
        select
            created_on at time zone 'utc' at time zone 'America/Vancouver' as created_pst,
            updated_on at time zone 'utc' at time zone 'america/vancouver' as updated_pst,
            pa.auth_account_id,
            pa.name,
            i.id as invoice_id,
            payment_method_code,
            invoice_number,
            filing_id,
            pa.bcol_account,
            created_by,
            created_name,
            invoice_status_code,
            total,
            paid,
            i.corp_type_code
        from
            invoices i
        left join payment_accounts pa on
            pa.id = i.payment_account_id
        left join invoice_references ir on
            i.id = ir.invoice_id
    """
    )


def downgrade():
    op.execute(
        """CREATE OR REPLACE VIEW RPT_INVOICES_PLI as
        select
            created_on at time zone 'utc' at time zone 'america/vancouver' as created_pst,
            updated_on at time zone 'utc' at time zone 'america/vancouver' as updated_pst,
            pa.auth_account_id,
            pa.name,
            i.id as invoice_id,
            payment_method_code,
            invoice_number,
            routing_slip,
            pli.total as pli_total,
            i.total as invoice_total,
            i.paid as invoice_paid,
            pli.service_fees as pli_service_fees,
            i.service_fees
        from
            invoices i
        left join invoice_references ir on
            i.id = ir.invoice_id
        left join payment_accounts pa on
            pa.id = i.payment_account_id
        left join payment_line_items pli on
            pli.invoice_id = i.id;
    """
    )
    op.execute(
        """CREATE OR REPLACE VIEW RPT_INVOICES as
        select
            created_on at time zone 'utc' at time zone 'America/Vancouver' as created_pst,
            updated_on at time zone 'utc' at time zone 'america/vancouver' as updated_pst,
            pa.auth_account_id,
            pa.name,
            i.id as invoice_id,
            payment_method_code,
            invoice_number,
            filing_id,
            pa.bcol_account,
            created_by,
            created_name,
            invoice_status_code,
            total,
            paid
        from
            invoices i
        left join payment_accounts pa on
            pa.id = i.payment_account_id
        left join invoice_references ir on
            i.id = ir.invoice_id
    """
    )
