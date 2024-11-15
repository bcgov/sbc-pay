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
"""transactions_materialized_view materialized view."""

from pay_api.models import db


class TransactionsMaterializedView(db.Model):
    """
    This model represents the `transactions_materialized_view` materialized view in the database.

    It is designed to improve query performance for purchase history and other related queries by
    pre-joining data from multiple tables, thereby reducing the need for complex joins in real-time queries.
    SELECT ... FROM invoices
    LEFT OUTER JOIN payment_accounts ON invoices.payment_account_id = payment_accounts.id
    LEFT OUTER JOIN payment_line_items ON payment_line_items.invoice_id = invoices.id
    LEFT OUTER JOIN fee_schedules ON fee_schedules.fee_schedule_id = payment_line_items.fee_schedule_id
    LEFT OUTER JOIN invoice_references ON invoice_references.invoice_id = invoices.id
    ORDER BY invoices.id DESC;

    Note:
    - This model should be treated as read-only.
    Any updates to the underlying tables will not automatically reflect in this materialized view
    until it is refreshed.
    - Use this model to query data in the materialized view rather than directly
    joining multiple tables when possible for performance benefits.
    """

    __tablename__ = 'transactions_materialized_view'
    __table_args__ = {'extend_existing': True}
    __mapper_args__ = {
        "include_properties": [
            "auth_account_id",
            "bcol_account",
            "billable",
            "business_identifier",
            "corp_type_code",
            "created_by",
            "created_name"
            "created_on",
            "description",
            "details",
            "disbursement_date",
            "disbursement_reversal_date",
            "fee_schedule_id",
            "filing_id",
            "filing_type_code",
            "folio_number",
            "gst",
            "invoice_id",
            "invoice_number",
            "invoice_reference_id",
            "invoice_reference_status_code",
            "invoice_status_code",
            "line_item_id",
            "overdue_date",
            "paid",
            "payment_account_id",
            "payment_account_name",
            "payment_date",
            "payment_method_code",
            "pst",
            "reference_number",
            "refund_date",
            "refund",
            "row_id",
            "service_fees",
            "total",
        ]
    }

    row_id = db.Column(db.Integer, primary_key=True)

    auth_account_id = db.Column(db.String(50), nullable=True)
    bcol_account = db.Column(db.String(50), nullable=True)
    billable = db.Column(db.Boolean, nullable=True)
    business_identifier = db.Column(db.String(20), nullable=True)
    corp_type_code = db.Column(db.String(10), nullable=True)
    created_by = db.Column(db.String(50), nullable=True)
    created_name = db.Column(db.String(100), nullable=True)
    created_on = db.Column(db.DateTime, nullable=True)
    description = db.Column(db.String(200), nullable=True)
    details = db.Column(db.String(200), nullable=True)
    disbursement_date = db.Column(db.Date, nullable=True)
    disbursement_reversal_date = db.Column(db.Date, nullable=True)
    fee_schedule_id = db.Column(db.Integer, nullable=True)
    filing_id = db.Column(db.Integer, nullable=True)
    filing_type_code = db.Column(db.String(10), nullable=True)
    folio_number = db.Column(db.String(50), nullable=True)
    gst = db.Column(db.Numeric(19, 2), nullable=True)
    invoice_id = db.Column(db.Integer, nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True)
    invoice_reference_id = db.Column(db.Integer, nullable=True)
    invoice_reference_status_code = db.Column(db.String(20), nullable=True)
    invoice_status_code = db.Column(db.String(20), nullable=True)
    line_item_id = db.Column(db.Integer, nullable=True)
    overdue_date = db.Column(db.DateTime, nullable=True)
    paid = db.Column(db.Numeric(19, 2), nullable=True)
    payment_account_id = db.Column(db.Integer, nullable=True)
    payment_account_name = db.Column(db.String(100), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    payment_method_code = db.Column(db.String(15), nullable=True)
    pst = db.Column(db.Numeric(19, 2), nullable=True)
    reference_number = db.Column(db.String(50), nullable=True)
    refund = db.Column(db.Numeric(19, 2), nullable=True)
    refund_date = db.Column(db.DateTime, nullable=True)
    service_fees = db.Column(db.Numeric(19, 2), nullable=True)
    total = db.Column(db.Numeric(19, 2), nullable=True)
