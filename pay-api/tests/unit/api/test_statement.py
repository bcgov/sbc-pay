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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""

from datetime import datetime, timezone
import json

from pay_api.models import PaymentAccount
from pay_api.models.invoice import Invoice
from pay_api.utils.enums import ContentType, InvoiceStatus, StatementFrequency
from pay_api.utils.util import get_local_formatted_date
from tests.utilities.base_test import (
    factory_statement, factory_statement_invoices, factory_statement_settings, get_claims, get_payment_request,
    token_header)


def test_get_daily_statements(session, client, jwt, app):
    """Assert that the default statement setting is daily."""
    # Create a payment account and statement details, then get all statements for the account

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements',
                    headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('total') == 1
    assert rv.json.get('items')[0].get('frequency') == StatementFrequency.DAILY.value


def test_get_daily_statements_verify_order(session, client, jwt, app):
    """Assert that the default statement setting is daily."""
    # Create a payment account and statement details, then get all statements for the account

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    factory_statement(payment_account_id=pay_account.id,
                      frequency=StatementFrequency.DAILY.value,
                      statement_settings_id=settings_model.id)
    factory_statement(payment_account_id=pay_account.id,
                      frequency=StatementFrequency.WEEKLY.value,
                      statement_settings_id=settings_model.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements',
                    headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('total') == 2
    # should come in the order latest first
    assert rv.json.get('items')[0].get('frequency') == StatementFrequency.WEEKLY.value
    assert rv.json.get('items')[1].get('frequency') == StatementFrequency.DAILY.value


def test_get_weekly_statements(session, client, jwt, app):
    """Assert that the default statement setting is weekly."""
    # Create a payment account and statement details, then get all statements for the account

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.WEEKLY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements',
                    headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('total') == 1
    assert rv.json.get('items')[0].get('frequency') == StatementFrequency.WEEKLY.value


def test_get_weekly_statement_report_as_pdf(session, client, jwt, app):
    """Assert that the weekly statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': ContentType.PDF.value
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.WEEKLY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}',
                    headers=headers)
    assert rv.status_code == 200


def test_get_monthly_statement_report_as_pdf(session, client, jwt, app):
    """Assert that the monthly statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': ContentType.PDF.value
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.MONTHLY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.MONTHLY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}',
                    headers=headers)
    assert rv.status_code == 200


def test_get_daily_statement_report_as_pdf(session, client, jwt, app):
    """Assert that the daily statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': ContentType.PDF.value
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}',
                    headers=headers)
    assert rv.status_code == 200


def test_get_monthly_statement_report_as_csv(session, client, jwt, app):
    """Assert that the monthly statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': ContentType.CSV.value
    }

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)

    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}',
                    headers=headers)
    assert rv.status_code == 200


def test_statement_summary(session, client, jwt, app):
    """Assert the statement summary is working."""
    headers = {
        'Authorization': f'Bearer {jwt.create_jwt(get_claims(), token_header)}',
        'content-type': 'application/json'
    }

    # Check if this works without any invoices in OVERDUE.
    rv = client.post('/api/v1/payment-requests',
                     data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                     headers=headers)
    invoice: Invoice = Invoice.find_by_id(rv.json.get('id'))
    payment_account_id = invoice.payment_account_id
    pay_account: PaymentAccount = PaymentAccount.find_by_id(payment_account_id)
    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements/summary',
                    headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('totalDue') == 0
    assert rv.json.get('oldestOverdueDate') is None

    # Create multiple OVERDUE invoices and check they add up.
    total_due = 0
    payment_account_id = 0
    invoice_ids = []
    oldest_overdue_date = datetime.now(tz=timezone.utc)
    for _ in range(5):
        rv = client.post('/api/v1/payment-requests',
                         data=json.dumps(get_payment_request(business_identifier='CP0002000')),
                         headers=headers)
        invoice_ids.append(rv.json.get('id'))

    for invoice_id in invoice_ids:
        invoice = Invoice.find_by_id(invoice_id)
        invoice.invoice_status_code = InvoiceStatus.OVERDUE.value
        invoice.overdue_date = oldest_overdue_date
        total_due += invoice.total - invoice.paid
        invoice.save()

    settings_model = factory_statement_settings(payment_account_id=pay_account.id,
                                                frequency=StatementFrequency.MONTHLY.value)
    statement_model = factory_statement(payment_account_id=pay_account.id,
                                        frequency=StatementFrequency.MONTHLY.value,
                                        statement_settings_id=settings_model.id)
    for invoice_id in invoice_ids:
        factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_id)

    rv = client.get(f'/api/v1/accounts/{pay_account.auth_account_id}/statements/summary',
                    headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('totalDue') == float(total_due)
    assert rv.json.get('oldestOverdueDate') == get_local_formatted_date(oldest_overdue_date)
