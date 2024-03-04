"""update refund payment date to invoices

Revision ID: d2d9864164d1
Revises: 0a3ad7c041f6
Create Date: 2023-02-23 10:14:27.347074

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'd2d9864164d1'
down_revision = '0a3ad7c041f6'
branch_labels = None
depends_on = None


def upgrade():
    """Update payment and refund date in invoices table."""
    # 1. Find all id and payment date from invoice table linking with invoice_reference table.
    # 2. Update payment_date with invoice_id.
    op.execute("set statement_timeout=20000;")
    conn = op.get_bind()
    res = conn.execute(text(f'select i.id as "id", p.payment_date as "date"\
                                from invoice_references ir \
                                inner join invoices i on i.id = ir.invoice_id \
                                inner join payments p on p.invoice_number = ir.invoice_number \
                                where p.payment_date IS NOT null AND i.payment_date IS null;'))
    payments = res.fetchall()
    for payment in payments:
        invoice_id = payment[0]
        payment_date = payment[1]
        op.execute(text(f"update invoices set payment_date=\'{payment_date}\' where id = {invoice_id}"))

    # 1. Find all id and refund date from invoice table linking with refunds table.
    # 2. Update refund_date with invoice_id.
    res = conn.execute(text(f'select i.id as "id", r.requested_date as "date"\
                                    from invoices i \
                                    inner join refunds r on r.invoice_id = i.id\
                                    where i.invoice_status_code = \'REFUNDED\'\
                                    and i.refund_date is null;'))
    refunds = res.fetchall()
    for refund in refunds:
        id = refund[0]
        refund_date = refund[1]
        op.execute(text(f"update invoices set refund_date=\'{refund_date}\' where id = {id}"))


def downgrade():
    pass
