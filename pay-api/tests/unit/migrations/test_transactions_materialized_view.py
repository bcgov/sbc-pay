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
from pay_api.utils.enums import DatabaseViews


def test_transactions_materialized_view_exists(app):
    """Test to ensure the transactions materialized view and index exist."""
    view_name = DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value
    index_name = DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW_IDX.value

    with app.app_context():
        view_exists = db.session.execute(
            text(f"SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = '{view_name}');")
        ).scalar()
        assert view_exists, f"Materialized view '{view_name}' does not exist."

        index_exists = db.session.execute(
            text(f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}');")
        ).scalar()
        assert index_exists, f"Index '{index_name}' on materialized view '{view_name}' does not exist."


def test_transactions_materialized_view_columns(app):
    """Test that the transactions materialized view has the correct columns."""
    expected_columns = {
        "row_id", "fee_schedule_id", "filing_type_code", "line_item_id", "description",
        "gst", "pst", "payment_account_id", "auth_account_id",
        "payment_account_name", "billable", "invoice_reference_id", "invoice_number",
        "reference_number", "invoice_reference_status_code", "invoice_id",
        "invoice_status_code", "payment_method_code", "corp_type_code",
        "disbursement_date", "disbursement_reversal_date", "created_on",
        "business_identifier", "total", "paid", "payment_date", "overdue_date",
        "refund_date", "refund", "filing_id", "folio_number", "bcol_account",
        "service_fees", "details", "created_by", "created_name"
    }

    view_name = DatabaseViews.TRANSACTIONS_MATERIALIZED_VIEW.value

    with app.app_context():
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
