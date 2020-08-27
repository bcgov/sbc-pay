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

"""Tests to assure the UpdateStalePayment .
Test-Suite to ensure that the UpdateStalePayment is working as expected.
"""
from jobs.statement_job import StatementJob
from .factory import *
from pay_api.utils.util import get_previous_day, get_first_and_last_dates_of_month
from datetime import datetime, timedelta
from pay_api.models import Statement, StatementInvoices
from dateutil.relativedelta import *


def test_statements(session):
    """Test dailiy statement generation works.

    Steps:
    1) Create a payment for yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement contains payment records
    """
    previous_day = get_previous_day(datetime.now())
    bcol_account = factory_premium_payment_account()
    payment = factory_payment(created_on=previous_day)
    invoice = factory_invoice(payment=payment, payment_account=bcol_account)
    factory_invoice_reference(invoice_id=invoice.id)
    factory_statement_settings(
        pay_account_id=bcol_account.account_id,
        from_date=previous_day,
        frequency='DAILY'
    )
    StatementJob.generate_statements()

    pay_account = PaymentAccount.find_by_id(bcol_account.account_id)

    statements = Statement.find_all_statements_for_account(auth_account_id=pay_account.auth_account_id, page=1,
                                                           limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert invoices is not None
    assert invoices[0].id == invoice.id


def test_statements_for_empty_results(session):
    """Test dailiy statement generation works.

    Steps:
    1) Create a payment for day before yesterday
    2) Mark the account settings as DAILY settlement starting yesterday
    3) Generate statement and assert that the statement does not contains payment records
    """
    day_before_yday = get_previous_day(datetime.now()) - timedelta(days=1)
    bcol_account = factory_premium_payment_account()
    payment = factory_payment(created_on=day_before_yday)
    invoice = factory_invoice(payment=payment, payment_account=bcol_account)
    factory_invoice_reference(invoice_id=invoice.id)
    factory_statement_settings(
        pay_account_id=bcol_account.account_id,
        from_date=day_before_yday,
        frequency='DAILY'
    )
    StatementJob.generate_statements()

    pay_account = PaymentAccount.find_by_id(bcol_account.account_id)

    statements = Statement.find_all_statements_for_account(auth_account_id=pay_account.auth_account_id, page=1,
                                                           limit=100)
    assert statements is not None
    invoices = StatementInvoices.find_all_invoices_for_statement(statements[0][0].id)
    assert len(invoices) == 0

