"""create transactions_materialized_view

Revision ID: 23b6d52daa41
Revises: 0f02d5964a63
Create Date: 2024-11-13 09:31:35.075717

"""
from alembic import op

from pay_api.utils.enums import DatabaseViews
from pay_api.models.payment import Payment


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '23b6d52daa41'
down_revision = '0f02d5964a63'
branch_labels = None
depends_on = None


def upgrade():
    """
    This model represents the `transactions_materialized_view` materialized view in the database.
    It is designed to improve query performance for purchase history and other related queries by
    pre-joining data from multiple tables, thereby reducing the need for complex joins in real-time queries.
    Note:
    - This model should be treated as read-only.
    Any updates to the underlying tables will not automatically reflect in this materialized view
    until it is refreshed.
    - Use this model to query data in the materialized view rather than directly
    joining multiple tables when possible for performance benefits.
    """
    base_query = Payment.generate_base_transaction_query()
    query_sql = str(base_query.statement.compile(compile_kwargs={"literal_binds": True}))
    op.execute("set statement_timeout=900000;")
    op.execute(f'''
        CREATE MATERIALIZED VIEW {DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value} AS
        {query_sql}
        ORDER BY id DESC;
    ''')

    op.execute(f'''
        CREATE INDEX {DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW_IDX.value}
        ON {DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value} (auth_account_id, id DESC);
    ''')


def downgrade():
    op.execute(f'''
        DROP INDEX IF EXISTS {DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW_IDX.value};
    ''')

    op.execute(f'''
        DROP MATERIALIZED VIEW IF EXISTS {DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value};
    ''')
