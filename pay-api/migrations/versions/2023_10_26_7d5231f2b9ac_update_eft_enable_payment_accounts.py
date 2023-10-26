"""18099-eft allowed flag

Revision ID: 7d5231f2b9ac
Revises: 2ef58b39cafc
Create Date: 2023-10-26 13:55:46.291450

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '7d5231f2b9ac'
down_revision = '2ef58b39cafc'
branch_labels = None
depends_on = None


def upgrade():
    """Update eft_enable in payment_accounts table."""
    # eft_enable set to true when it has invoices paid with EFT/DIRECT_PAY payment method historically
    op.execute("set statement_timeout=20000;")
    conn = op.get_bind()
    conn.execute('UPDATE payment_accounts \
                            SET eft_enable = true \
                            WHERE id IN ( \
                                SELECT pa.id \
                                FROM payment_accounts pa \
                                RIGHT JOIN invoices i ON i.payment_account_id = pa.id \
                                WHERE i.payment_method_code IN (\'EFT\', \'DIRECT_PAY\') \
                            )')

def downgrade():
    pass
