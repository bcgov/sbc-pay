"""Add in payment methods string column, this way we don't need to look at payment method history and we don't 
   have bad performance looking at statements invoices.

Revision ID: 5cb9c5f5896c
Revises: 17ca5cd561ca
Create Date: 2024-08-08 22:01:40.129963

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '5cb9c5f5896c'
down_revision = '17ca5cd561ca'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('statements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_methods', sa.String(length=100), nullable=True))

    # Scenario where there are no statement invoices.
    # Note this takes at least 15 minutes to run both queries.
    op.execute("""
        update
            statements
        set
            (payment_methods) = (
            select
                payment_method
            from
                payment_accounts
            where
                payment_accounts.id = statements.payment_account_id
        )
        where payment_methods is null and not exists (select 1 from statement_invoices where statement_invoices.statement_id = statements.id);
    """)

    # Scenario where there exists statement invoices.
    op.execute("""
        update
            statements
        set
            (payment_methods) = (
            select
                string_agg(distinct payment_method_code, ',')
            from
                statement_invoices
            join invoices on
                invoices.id = statement_invoices.invoice_id
            where
                statement_invoices.statement_id = statements.id
            group by statement_invoices.statement_id
        )
        where payment_methods is null;
    """)

def downgrade():
    with op.batch_alter_table('statements', schema=None) as batch_op:
        batch_op.drop_column('payment_methods')
