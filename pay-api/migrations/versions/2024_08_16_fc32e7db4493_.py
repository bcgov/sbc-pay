"""Add in fields we can easily check and return to clients.

Revision ID: fc32e7db4493
Revises: 4410b7fc6437
Create Date: 2024-08-16 12:36:57.797210

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = 'fc32e7db4493'
down_revision = '4410b7fc6437'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_nsf_invoices', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('has_overdue_invoices', sa.DateTime(), nullable=True))

    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_nsf_invoices', sa.DateTime(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('has_overdue_invoices', sa.DateTime(), autoincrement=False, nullable=True))

    op.execute("update payment_accounts pa set has_nsf_invoices = (select now() from cfs_accounts ca where ca.account_id = pa.id and ca.status = \'FREEZE\' and ca.payment_method = \'PAD\' limit 1)")
    op.execute("update payment_accounts pa set has_overdue_invoices = (select now() from invoices i where i.payment_method_code = 'EFT' and i.payment_account_id = pa.id and i.invoice_status_code = \'OVERDUE\' limit 1)")

def downgrade():
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.drop_column('has_overdue_invoices')
        batch_op.drop_column('has_nsf_invoices')

    with op.batch_alter_table('payment_accounts', schema=None) as batch_op:
        batch_op.drop_column('has_overdue_invoices')
        batch_op.drop_column('has_nsf_invoices')
