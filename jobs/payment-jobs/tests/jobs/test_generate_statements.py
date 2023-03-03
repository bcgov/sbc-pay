# Copyright © 2019 Province of British Columbia
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

"""Tests to assure the UpdateStalePayment.

Test-Suite to ensure that the UpdateStalePayment is working as expected.
"""
from datetime import datetime, timedelta

from pay_api.models import Statement, StatementInvoices
from pay_api.utils.util import get_previous_day

from tasks.statement_task import StatementTask

from .factory import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_premium_payment_account,
    factory_statement_settings)


def test_statements(session):
    """Test daily statement generation works.

    Steps:
    1) Create a payment for yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement contains payment records
    """
    previous_day = get_previous_day(datetime.now())
    bcol_account = factory_premium_payment_account()
    invoice = factory_invoice(payment_account=bcol_account, created_on=previous_day)
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(payment_date=previous_day, invoice_number=inv_ref.invoice_number)

    factory_statement_settings(
        pay_account_id=bcol_account.id,
        from_date=previous_day,
        frequency='DAILY'
    )
    StatementTask.generate_statements()

    statements = Statement.find_all_statements_for_account(auth_account_id=bcol_account.auth_account_id, page=1,
                                                           limit=100)
    assert statements is not None
    first_statement_id = statements[0][0].id
    invoices = StatementInvoices.find_all_invoices_for_statement(first_statement_id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Test date override.
    # Override computes for the target date, not the previous date like above.
    StatementTask.generate_statements((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))

    statements = Statement.find_all_statements_for_account(auth_account_id=bcol_account.auth_account_id, page=1,
                                                           limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].invoice_id == invoice.id

    # Check to see if the old statement / invoices were cleaned up.
    assert Statement.find_by_id(first_statement_id) is None
    assert StatementInvoices.find_all_invoices_for_statement(first_statement_id) == []


def test_statements_for_empty_results(session):
    """Test daily statement generation works.

    Steps:
    1) Create a payment for day before yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement does not contains payment records
    """
    day_before_yday = get_previous_day(datetime.now()) - timedelta(days=1)
    bcol_account = factory_premium_payment_account()
    invoice = factory_invoice(payment_account=bcol_account, created_on=day_before_yday)
    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_statement_settings(
        pay_account_id=bcol_account.id,
        from_date=day_before_yday,
        frequency='DAILY'
    )
    factory_payment(payment_date=day_before_yday, invoice_number=inv_ref.invoice_number)

    StatementTask.generate_statements()

    statements = Statement.find_all_statements_for_account(auth_account_id=bcol_account.auth_account_id, page=1,
                                                           limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert len(invoices) == 0
