"""create transactions_materialized_view

Revision ID: 23b6d52daa41
Revises: 0f02d5964a63
Create Date: 2024-11-13 09:31:35.075717

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import DatabaseViews
from pay_api.utils.serializable import Serializable


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '23b6d52daa41'
down_revision = '0f02d5964a63'
branch_labels = None
depends_on = None


def upgrade():
    base_query = Serializable.generate_base_transaction_query()
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
