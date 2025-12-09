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

import json
from datetime import UTC, datetime
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from pay_api.models import PaymentAccount
from pay_api.models.fee_schedule import FeeSchedule
from pay_api.models.invoice import Invoice
from pay_api.services.report_service import ReportService
from pay_api.utils.enums import ContentType, InvoiceStatus, PaymentMethod, StatementFrequency
from tests.utilities.base_test import (
    factory_applied_credits,
    factory_credit,
    factory_eft_credit,
    factory_eft_file,
    factory_eft_shortname,
    factory_eft_shortname_link,
    factory_invoice,
    factory_payment_account,
    factory_payment_line_item,
    factory_refunds_partial,
    factory_statement,
    factory_statement_invoices,
    factory_statement_settings,
    get_claims,
    get_payment_request,
    get_payment_request_with_payment_method,
    token_header,
)


def test_get_daily_statements(session, client, jwt, app):
    """Assert that the default statement setting is daily."""
    # Create a payment account and statement details, then get all statements for the account

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f"/api/v1/accounts/{pay_account.auth_account_id}/statements", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("total") == 1
    assert rv.json.get("items")[0].get("frequency") == StatementFrequency.DAILY.value


def test_get_daily_statements_verify_order(session, client, jwt, app):
    """Assert that the default statement setting is daily."""
    # Create a payment account and statement details, then get all statements for the account

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.DAILY.value
    )
    factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.WEEKLY.value,
        statement_settings_id=settings_model.id,
    )

    rv = client.get(f"/api/v1/accounts/{pay_account.auth_account_id}/statements", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("total") == 2
    # should come in the order latest first
    assert rv.json.get("items")[0].get("frequency") == StatementFrequency.WEEKLY.value
    assert rv.json.get("items")[1].get("frequency") == StatementFrequency.DAILY.value


def test_get_weekly_statements(session, client, jwt, app):
    """Assert that the default statement setting is weekly."""
    # Create a payment account and statement details, then get all statements for the account

    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.WEEKLY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(f"/api/v1/accounts/{pay_account.auth_account_id}/statements", headers=headers)
    assert rv.status_code == 200
    assert rv.json.get("total") == 1
    assert rv.json.get("items")[0].get("frequency") == StatementFrequency.WEEKLY.value


def test_get_weekly_statement_report_as_pdf(session, client, jwt, app):
    """Assert that the weekly statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": ContentType.PDF.value,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.WEEKLY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}",
        headers=headers,
    )
    assert rv.status_code == 200
    assert "Content-Length" not in rv.headers


def test_get_monthly_statement_report_as_pdf(session, client, jwt, app):
    """Assert that the monthly statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": ContentType.PDF.value,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}",
        headers=headers,
    )
    assert rv.status_code == 200
    assert "Content-Length" not in rv.headers


def test_get_daily_statement_report_as_pdf(session, client, jwt, app):
    """Assert that the daily statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": ContentType.PDF.value,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}",
        headers=headers,
    )
    assert rv.status_code == 200
    assert "Content-Length" not in rv.headers


def test_get_monthly_statement_report_as_csv(session, client, jwt, app):
    """Assert that the monthly statement report is returning response."""
    # Create a payment account and statement details, then get all statements for the account
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": ContentType.CSV.value,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}",
        headers=headers,
    )
    assert rv.status_code == 200
    assert "Content-Length" not in rv.headers


def test_statement_summary(session, client, jwt, app):
    """Assert the statement summary is working."""
    headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }

    # Check if this works without any invoices in OVERDUE.
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )
    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    payment_account_id = invoice.payment_account_id
    pay_account: PaymentAccount = PaymentAccount.find_by_id(payment_account_id)
    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("totalDue") == 0
    assert rv.json.get("oldestDueDate") is None

    # Create multiple OVERDUE invoices and check they add up.
    total_due = 0
    payment_account_id = 0
    invoice_ids = []
    oldest_due_date = datetime.now(tz=UTC) + relativedelta(months=1)
    for _ in range(5):
        rv = client.post(
            "/api/v1/payment-requests",
            data=json.dumps(
                get_payment_request_with_payment_method(
                    business_identifier="CP0002000",
                    payment_method=PaymentMethod.EFT.value,
                )
            ),
            headers=headers,
        )
        invoice_ids.append(rv.json.get("id"))

    for invoice_id in invoice_ids:
        invoice = Invoice.find_by_id(invoice_id)
        invoice.invoice_status_code = InvoiceStatus.OVERDUE.value
        total_due += invoice.total - invoice.paid
        invoice.save()

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
    )
    for invoice_id in invoice_ids:
        factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("totalDue") == float(total_due)
    assert rv.json.get("oldestDueDate") == (oldest_due_date.date() + relativedelta(hours=8)).isoformat()
    assert rv.json.get("shortNameLinksCount") == 0
    assert rv.json.get("isEftUnderPayment") is None


def test_statement_summary_with_eft_invoices_no_statement(session, client, jwt, app):
    """Assert the statement summary is working when eft invoices has no statement yet."""
    headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }

    invoice_ids = []
    unpaid_amount = 0
    for _ in range(3):
        rv = client.post(
            "/api/v1/payment-requests",
            data=json.dumps(
                get_payment_request_with_payment_method(
                    business_identifier="CP0002000",
                    payment_method=PaymentMethod.EFT.value,
                )
            ),
            headers=headers,
        )
        invoice_id = rv.json.get("id")
        invoice = Invoice.find_by_id(invoice_id)
        invoice.invoice_status_code = InvoiceStatus.APPROVED.value
        invoice.save()
        invoice_ids.append(invoice_id)
        unpaid_amount += invoice.total - invoice.paid

    payment_account_id = Invoice.find_by_id(invoice_ids[0]).payment_account_id
    pay_account = PaymentAccount.find_by_id(payment_account_id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/summary",
        headers=headers,
    )

    assert rv.status_code == 200
    assert rv.json.get("totalDue") == 0
    assert rv.json.get("oldestDueDate") is None
    assert rv.json.get("totalInvoiceDue") == float(unpaid_amount)
    assert rv.json.get("shortNameLinksCount") == 0
    assert rv.json.get("isEftUnderPayment") is None


def test_statement_summary_single_eft_under_payment(session, client, jwt, app):
    """Assert the statement summary EFT under payment flag is working as expected for single link."""
    headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }
    pay_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value).save()
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME1").save()
    factory_eft_shortname_link(
        short_name_id=short_name.id,
        auth_account_id=pay_account.auth_account_id,
        updated_by="TEST",
    ).save()
    invoice = factory_invoice(
        payment_account=pay_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=10,
    ).save()
    eft_file = factory_eft_file().save()
    factory_eft_credit(
        eft_file_id=eft_file.id,
        short_name_id=short_name.id,
        amount=10,
        remaining_amount=10,
    ).save()
    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("shortNameLinksCount") == 1
    assert rv.json.get("isEftUnderPayment") is False

    invoice.total = 11
    invoice.save()

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("shortNameLinksCount") == 1
    assert rv.json.get("isEftUnderPayment") is True


def test_statement_summary_multi_eft_under_payment(session, client, jwt, app):
    """Assert the statement summary EFT under payment flag is working as expected for multi link."""
    headers = {
        "Authorization": f"Bearer {jwt.create_jwt(get_claims(), token_header)}",
        "content-type": "application/json",
    }
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME1").save()
    pay_account1 = factory_payment_account(payment_method_code=PaymentMethod.EFT.value, auth_account_id="1111").save()
    pay_account2 = factory_payment_account(payment_method_code=PaymentMethod.EFT.value, auth_account_id="2222").save()
    eft_file = factory_eft_file().save()
    factory_eft_shortname_link(
        short_name_id=short_name.id,
        auth_account_id=pay_account1.auth_account_id,
        updated_by="TEST",
    ).save()
    factory_eft_shortname_link(
        short_name_id=short_name.id,
        auth_account_id=pay_account2.auth_account_id,
        updated_by="TEST",
    ).save()
    invoice1 = factory_invoice(
        payment_account=pay_account1,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=5,
    ).save()
    invoice2 = factory_invoice(
        payment_account=pay_account2,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=6,
    ).save()
    invoices_total = invoice1.total + invoice2.total
    eft_credits = factory_eft_credit(
        eft_file_id=eft_file.id,
        short_name_id=short_name.id,
        amount=invoices_total,
        remaining_amount=invoices_total,
    ).save()
    settings_model = factory_statement_settings(
        payment_account_id=pay_account1.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement_model = factory_statement(
        payment_account_id=pay_account1.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice1.id)

    settings_model2 = factory_statement_settings(
        payment_account_id=pay_account2.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement_model2 = factory_statement(
        payment_account_id=pay_account2.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model2.id,
    )
    factory_statement_invoices(statement_id=statement_model2.id, invoice_id=invoice2.id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account1.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("totalDue") == invoice1.total
    assert rv.json.get("shortNameLinksCount") == 2
    assert rv.json.get("isEftUnderPayment") is False

    rv = client.get(
        f"/api/v1/accounts/{pay_account2.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("totalDue") == invoice2.total
    assert rv.json.get("shortNameLinksCount") == 2
    assert rv.json.get("isEftUnderPayment") is False

    eft_credits.remaining_amount = invoices_total - 1
    eft_credits.save()

    rv = client.get(
        f"/api/v1/accounts/{pay_account1.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("totalDue") == invoice1.total
    assert rv.json.get("shortNameLinksCount") == 2
    assert rv.json.get("isEftUnderPayment") is True

    rv = client.get(
        f"/api/v1/accounts/{pay_account2.auth_account_id}/statements/summary",
        headers=headers,
    )
    assert rv.status_code == 200
    assert rv.json.get("totalDue") == invoice2.total
    assert rv.json.get("shortNameLinksCount") == 2
    assert rv.json.get("isEftUnderPayment") is True


def test_statement_pad_totals_with_credits(session, client, jwt, app):
    """Assert that PAD statement with credits shows creditsApplied and credited transactions."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "Accept": ContentType.PDF.value,
    }

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(
            get_payment_request_with_payment_method(
                business_identifier="CP0002000",
                payment_method=PaymentMethod.PAD.value,
            )
        ),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    statement_from_date = datetime(2025, 12, 1, tzinfo=UTC)
    statement_to_date = datetime(2025, 12, 31, tzinfo=UTC)

    invoice.paid = 50.00
    invoice.created_on = datetime(2025, 12, 5, tzinfo=UTC)
    invoice.payment_date = datetime(2025, 12, 10, tzinfo=UTC)
    invoice.invoice_status_code = "PAID"
    invoice.save()

    credit = factory_credit(
        account_id=pay_account.id,
        cfs_identifier="TEST_CREDIT_PAD",
        amount=10.00,
        remaining_amount=10.00,
    )

    applied_credit = factory_applied_credits(
        invoice_id=invoice.id,
        credit_id=credit.id,
        invoice_number=f"INV_{invoice.id}",
        amount_applied=10.00,
        invoice_amount=invoice.total,
        cfs_identifier="TEST_CREDIT_PAD",
    )

    applied_credit.created_on = datetime(2025, 12, 6, tzinfo=UTC)
    applied_credit.save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line_item = factory_payment_line_item(
        invoice_id=invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
    )
    line_item.save()

    factory_refunds_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line_item.id,
        refund_amount=10.00,
        created_on=datetime(2025, 12, 7, tzinfo=UTC),
    )
    invoice.refund = 10.00
    invoice.refund_date = datetime(2025, 12, 7, tzinfo=UTC)

    settings_model = factory_statement_settings(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        from_date=statement_from_date,
    )
    statement_model = factory_statement(
        payment_account_id=pay_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        payment_methods=PaymentMethod.PAD.value,
        statement_settings_id=settings_model.id,
        from_date=statement_from_date,
        to_date=statement_to_date,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice.id)

    with patch.object(ReportService, "get_report_response", return_value=None) as mock_report:
        rv = client.get(
            f"/api/v1/accounts/{pay_account.auth_account_id}/statements/{statement_model.id}",
            headers=headers,
        )

        assert rv.status_code == 200

        call_args = mock_report.call_args[0][0]
        template_vars = call_args.template_vars

        assert len(template_vars["groupedInvoices"]) == 1

        grouped_invoice = template_vars["groupedInvoices"][0]

        assert grouped_invoice["paymentMethod"] == PaymentMethod.PAD.value

        assert "creditsApplied" in grouped_invoice
        assert grouped_invoice["creditsApplied"] == "10.00"

        assert "totals" in grouped_invoice
        assert grouped_invoice["totals"] == "30.00"

        assert "paid" in grouped_invoice
        assert grouped_invoice["paid"] == "30.00"

        assert "countedRefund" in grouped_invoice
        assert grouped_invoice["countedRefund"] == "10.00"
