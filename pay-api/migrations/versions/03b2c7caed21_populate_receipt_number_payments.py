"""populate_receipt_number_payments

Revision ID: 03b2c7caed21
Revises: c871202927f0
Create Date: 2021-07-28 10:10:39.460915

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '03b2c7caed21'
down_revision = 'c871202927f0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    res = conn.execute(text(f"select id, invoice_number from payments where receipt_number is null;"))
    results = res.fetchall()
    for result in results:
        pay_id = result[0]
        invoice_number = result[1]
        res = conn.execute(text(f"select r.receipt_number from receipts r left join invoice_references ir "
                           f"on ir.invoice_id=r.invoice_id where ir.status_code='COMPLETED' "
                           f"and invoice_number='{invoice_number}'"))
        receipt_number_result = res.fetchall()
        if receipt_number_result:
            receipt_number = receipt_number_result[0][0]
            op.execute(f"update payments set receipt_number='{receipt_number}' where id = {pay_id}")


def downgrade():
    pass
