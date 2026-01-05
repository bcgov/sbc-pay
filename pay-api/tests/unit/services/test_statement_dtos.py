# Copyright © 2025 Province of British Columbia
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

"""Tests for Statement DTOs - PAD Scenarios."""

from datetime import UTC, datetime

from pay_api.services.statement import Statement as StatementService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from pay_api.utils.statement_dtos import GroupedInvoicesDTO, StatementSummaryDTO
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment_account,
    factory_payment_line_item,
    factory_statement,
    factory_statement_invoices,
    factory_statement_settings,
)


def _create_statement_period(pay_account, from_date, to_date, pad_credit=0.00):
    """Helper to create statement settings and statement."""
    settings = factory_statement_settings(
        payment_account_id=pay_account.id,
        frequency="WEEKLY",
        from_date=from_date,
        to_date=to_date,
    )
    statement = factory_statement(
        payment_account_id=pay_account.id,
        frequency="WEEKLY",
        statement_settings_id=settings.id,
        from_date=from_date.date(),
        to_date=to_date.date(),
    )
    if pad_credit != 0.00:
        statement.pad_credit = pad_credit
        statement.save()
    return settings, statement


def _create_invoice_with_line_item(
    pay_account, total, service_fees, paid, status, payment_date, created_on, refund=None, refund_date=None
):
    """Helper to create invoice with line item and reference."""
    invoice = factory_invoice(
        payment_account=pay_account,
        total=total,
        service_fees=service_fees,
        paid=paid,
        payment_method_code=PaymentMethod.PAD.value,
        status_code=status,
        payment_date=payment_date,
        created_on=created_on,
        refund=refund,
        refund_date=refund_date,
    )
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1, total=total - service_fees).save()
    return invoice


def _get_pad_summary(statement_id, statement_to_date):
    """Helper to get PAD summary from statement."""
    invoices_query = StatementService.find_all_payments_and_invoices_for_statement(
        statement_id, PaymentMethod.PAD.value, statement_to_date=statement_to_date
    )
    db_summaries = StatementService.get_totals_by_payment_method_from_db(invoices_query, statement_to_date)
    return db_summaries.summaries.get(PaymentMethod.PAD.value)


def test_pad_scenario_1_no_credits(session):
    """Scenario 1: No credits - Balance: $0, Total: $266, PAD: $234.50, Due: $31.50."""
    pay_account = factory_payment_account(payment_method_code=PaymentMethod.PAD.value)
    pay_account.save()

    _, prev_statement = _create_statement_period(
        pay_account, datetime(2025, 11, 2, tzinfo=UTC), datetime(2025, 11, 8, tzinfo=UTC)
    )

    _, statement = _create_statement_period(
        pay_account, datetime(2025, 11, 9, tzinfo=UTC), datetime(2025, 11, 15, tzinfo=UTC)
    )

    invoice = _create_invoice_with_line_item(
        pay_account,
        266.00,
        6.00,
        234.50,
        InvoiceStatus.PAID.value,
        datetime(2025, 11, 12, tzinfo=UTC),
        datetime(2025, 11, 10, tzinfo=UTC),
    )
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    pad_summary = _get_pad_summary(statement.id, statement.to_date)

    assert pad_summary.totals == 266.00
    assert pad_summary.paid == 234.50
    assert pad_summary.credits_applied == 0.00
    assert pad_summary.counted_refund == 0.00
    assert pad_summary.due == 31.50


def test_pad_scenario_2_credits_refunded_during_month(session):
    """Scenario 2: Credits refunded during month - Balance: $31.50, Total: $266, Credits: $101.50, PAD: $133, Due: $63."""
    pay_account = factory_payment_account(payment_method_code=PaymentMethod.PAD.value)
    pay_account.save()

    _, prev_statement = _create_statement_period(
        pay_account, datetime(2025, 11, 2, tzinfo=UTC), datetime(2025, 11, 8, tzinfo=UTC)
    )

    prev_invoice = _create_invoice_with_line_item(
        pay_account,
        31.50,
        0.00,
        31.50,
        InvoiceStatus.APPROVED.value,
        None,
        datetime(2025, 11, 5, tzinfo=UTC),
    )
    factory_statement_invoices(statement_id=prev_statement.id, invoice_id=prev_invoice.id)

    _, statement = _create_statement_period(
        pay_account, datetime(2025, 11, 9, tzinfo=UTC), datetime(2025, 11, 15, tzinfo=UTC)
    )

    invoice = _create_invoice_with_line_item(
        pay_account,
        266.00,
        6.00,
        133.00,
        InvoiceStatus.PAID.value,
        datetime(2025, 11, 12, tzinfo=UTC),
        datetime(2025, 11, 10, tzinfo=UTC),
        101.50,
        datetime(2025, 11, 13, tzinfo=UTC),
    )
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    invoices_query = StatementService.find_all_payments_and_invoices_for_statement(
        statement.id,
        PaymentMethod.PAD.value,
        is_pdf_statement=True,
        statement_to_date=statement.to_date,
        add_refund_id=True,
    )
    db_summaries = StatementService.get_totals_by_payment_method_from_db(invoices_query, statement.to_date)
    invoices_orm = invoices_query.all()
    invoices_orm = [(invoice := row[0], setattr(invoice, "refund_id", row[1]))[0] for row in invoices_orm]

    db_summary = db_summaries.summaries.get(PaymentMethod.PAD.value)

    statement_summary_dict = {
        "lastStatementTotal": 31.50,
        "lastStatementPaidAmount": 0.00,
        "balanceForward": 31.50,
        "cancelledTransactions": 0,
        "latestStatementPaymentDate": None,
        "dueDate": None,
        "creditBalance": None,
    }

    statement_summary = StatementSummaryDTO.from_dict(statement_summary_dict)

    grouped_invoice = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.PAD.value,
        invoices_orm=invoices_orm,
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement.to_date,
        is_first=True,
    )

    assert grouped_invoice.totals == 164.50
    assert grouped_invoice.counted_refund == 101.50
    assert grouped_invoice.paid == 133.00
    assert grouped_invoice.due == 63.00


def test_pad_scenario_3_credits_refunded_after_pad_processed(session):
    """Scenario 3: Credits after PAD - Balance: $63, Total: $266, Credits: $300, PAD: $266, Due: -$34."""
    pay_account = factory_payment_account(payment_method_code=PaymentMethod.PAD.value)
    pay_account.save()

    _, prev_statement = _create_statement_period(
        pay_account, datetime(2025, 11, 2, tzinfo=UTC), datetime(2025, 11, 8, tzinfo=UTC)
    )

    prev_invoice = _create_invoice_with_line_item(
        pay_account,
        63.00,
        0.00,
        63.00,
        InvoiceStatus.PAID.value,
        None,
        datetime(2025, 11, 5, tzinfo=UTC),
    )
    factory_statement_invoices(statement_id=prev_statement.id, invoice_id=prev_invoice.id)

    _, statement = _create_statement_period(
        pay_account, datetime(2025, 11, 9, tzinfo=UTC), datetime(2025, 11, 15, tzinfo=UTC), 300.00
    )

    invoice = _create_invoice_with_line_item(
        pay_account,
        266.00,
        6.00,
        266.00,
        InvoiceStatus.PAID.value,
        datetime(2025, 11, 12, tzinfo=UTC),
        datetime(2025, 11, 10, tzinfo=UTC),
        300.00,
        datetime(2025, 11, 13, tzinfo=UTC),
    )
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    invoices_query = StatementService.find_all_payments_and_invoices_for_statement(
        statement.id,
        PaymentMethod.PAD.value,
        is_pdf_statement=True,
        statement_to_date=statement.to_date,
        add_refund_id=True,
    )
    db_summaries = StatementService.get_totals_by_payment_method_from_db(invoices_query, statement.to_date)
    invoices_orm = invoices_query.all()
    invoices_orm = [(invoice := row[0], setattr(invoice, "refund_id", row[1]))[0] for row in invoices_orm]

    db_summary = db_summaries.summaries.get(PaymentMethod.PAD.value)

    statement_summary_dict = {
        "lastStatementTotal": 63.00,
        "lastStatementPaidAmount": 63.00,
        "balanceForward": 0.00,
        "cancelledTransactions": 0,
        "latestStatementPaymentDate": None,
        "dueDate": None,
        "creditBalance": None,
    }

    statement_summary = StatementSummaryDTO.from_dict(statement_summary_dict)

    grouped_invoice = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.PAD.value,
        invoices_orm=invoices_orm,
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement.to_date,
        is_first=True,
    )

    assert grouped_invoice.totals == -34.00
    assert grouped_invoice.counted_refund == 300.00
    assert grouped_invoice.paid == 266.00
    assert grouped_invoice.due == -300.00


def test_pad_scenario_4_credits_carried_forward(session):
    """Scenario 4: Credits carried forward - Balance: -$300, Total: $266, Credits: $266, PAD: $0, Due: -$300."""
    from tests.utilities.base_test import factory_applied_credits

    pay_account = factory_payment_account(payment_method_code=PaymentMethod.PAD.value)
    pay_account.save()

    _, prev_statement = _create_statement_period(
        pay_account, datetime(2025, 11, 2, tzinfo=UTC), datetime(2025, 11, 8, tzinfo=UTC), 300.00
    )

    _, statement = _create_statement_period(
        pay_account, datetime(2025, 11, 9, tzinfo=UTC), datetime(2025, 11, 15, tzinfo=UTC)
    )

    invoice = _create_invoice_with_line_item(
        pay_account,
        266.00,
        6.00,
        266.00,
        InvoiceStatus.PAID.value,
        datetime(2025, 11, 12, tzinfo=UTC),
        datetime(2025, 11, 10, tzinfo=UTC),
    )
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    factory_applied_credits(
        invoice_id=invoice.id,
        credit_id=None,
        invoice_number=f"INV_{invoice.id}",
        amount_applied=266.00,
        invoice_amount=266.00,
        cfs_identifier="CREDIT_CARRIED_FORWARD",
        cfs_account="PAD_ACCOUNT",
        created_on=datetime(2025, 11, 12, tzinfo=UTC),
    )

    invoices_query = StatementService.find_all_payments_and_invoices_for_statement(
        statement.id,
        PaymentMethod.PAD.value,
        is_pdf_statement=True,
        statement_to_date=statement.to_date,
        add_refund_id=True,
    )
    db_summaries = StatementService.get_totals_by_payment_method_from_db(invoices_query, statement.to_date)
    invoices_orm = invoices_query.all()
    invoices_orm = [(invoice := row[0], setattr(invoice, "refund_id", row[1]))[0] for row in invoices_orm]

    db_summary = db_summaries.summaries.get(PaymentMethod.PAD.value)

    statement_summary_dict = {
        "lastStatementTotal": 0.00,
        "lastStatementPaidAmount": 0.00,
        "balanceForward": -300.00,
        "cancelledTransactions": 0,
        "latestStatementPaymentDate": None,
        "dueDate": None,
        "creditBalance": 300.00,
    }

    statement_summary = StatementSummaryDTO.from_dict(statement_summary_dict)

    grouped_invoice = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.PAD.value,
        invoices_orm=invoices_orm,
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement.to_date,
        is_first=True,
    )

    assert grouped_invoice.totals == 0.00
    assert grouped_invoice.credits_applied == 266.00
    assert grouped_invoice.paid == 0.00
    assert grouped_invoice.due == -34.00
