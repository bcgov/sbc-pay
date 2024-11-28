# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests to assure the Transactions Materialized View exist."""
from sqlalchemy import text

from pay_api.models import db
from pay_api.models.payment import Payment
from pay_api.utils.enums import DatabaseViews

# TODO remove perhaps
def test_transactions_materialized_view_exists(session):
    """Test to ensure the transactions materialized view and index exist."""
    view_name = DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value
    index_name = DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW_IDX.value

    view_exists = db.session.execute(
        text(f"SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = '{view_name}');")
    ).scalar()
    assert view_exists, f"Materialized view '{view_name}' does not exist."

    index_exists = db.session.execute(
        text(f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}');")
    ).scalar()
    assert index_exists, f"Index '{index_name}' on materialized view '{view_name}' does not exist."


def test_transactions_materialized_view_columns(session):
    """Test that the transactions materialized view has the correct columns."""
    # TODO repurpose this to do a runtime check.
    base_query = Payment.generate_base_transaction_query()
    expected_columns = {getattr(column, 'key') for column in base_query.statement.columns}
    view_name = DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value

    db.session.execute(text(f"REFRESH MATERIALIZED VIEW {view_name};"))
    db.session.commit()

    result = db.session.execute(text(f"""
        SELECT a.attname AS column_name
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'm'
            AND c.relname = '{view_name}'
            AND a.attnum > 0
            AND NOT a.attisdropped;
    """))
    actual_columns = {row[0] for row in result}

    missing_columns = expected_columns - actual_columns
    extra_columns = actual_columns - expected_columns

    assert not missing_columns, f"Missing columns in materialized view: {missing_columns}"
    assert not extra_columns, f"Extra columns in materialized view: {extra_columns}"
