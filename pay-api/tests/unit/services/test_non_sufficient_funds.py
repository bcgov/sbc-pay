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

"""Tests to assure the Non-Sufficient Funds service layer.

Test-Suite to ensure that the Non-Sufficient Funds layer is working as expected.
"""

import pytest

from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.services import NonSufficientFundsService
from pay_api.utils.enums import InvoiceStatus, StatementFrequency
from tests.utilities.base_test import (
    factory_distribution_code,
    factory_distribution_link,
    factory_invoice,
    factory_invoice_reference,
    factory_non_sufficient_funds,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_statement,
    factory_statement_invoices,
    factory_statement_settings,
)


def test_save_non_sufficient_funds(session):
    """Test save_non_sufficient_funds."""
    payment_account = factory_payment_account()
    payment = factory_payment(invoice_number="REG00000001")
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()
    non_sufficient_funds = NonSufficientFundsService.save_non_sufficient_funds(
        invoice_id=invoice.id,
        invoice_number=payment.invoice_number,
        cfs_account="1234567890",
        description="NSF",
    )
    assert non_sufficient_funds
    assert non_sufficient_funds["description"] == "NSF"


def test_find_all_non_sufficient_funds_invoices(session):
    """Test find_all_non_sufficient_funds_invoices."""
    payment_account = factory_payment_account()
    payment_account.save()
    payment = factory_payment(
        payment_account_id=payment_account.id,
        paid_amount=0,
        invoice_number="REG00000001",
        payment_method_code="PAD",
    )
    payment.save()
    invoice = factory_invoice(
        payment_account=payment_account,
        status_code=InvoiceStatus.SETTLEMENT_SCHEDULED.value,
        paid=0,
        total=30,
    )
    invoice.save()

    annual_report_fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    annual_report_payment_line_item = factory_payment_line_item(
        invoice_id=invoice.id,
        fee_schedule_id=annual_report_fee_schedule.fee_schedule_id,
        description="Annual Report",
        total=30,
        filing_fees=0,
    )
    annual_report_payment_line_item.save()

    non_sufficient_funds_fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("BCR", "NSF")
    distribution_code = factory_distribution_code("NSF")
    distribution_code.save()
    distribution_link = factory_distribution_link(
        distribution_code.distribution_code_id,
        non_sufficient_funds_fee_schedule.fee_schedule_id,
    )
    distribution_link.save()
    non_sufficient_funds_payment_line_item = factory_payment_line_item(
        invoice_id=invoice.id,
        fee_schedule_id=non_sufficient_funds_fee_schedule.fee_schedule_id,
        description="NSF",
        total=30,
        filing_fees=0,
    )
    non_sufficient_funds_payment_line_item.save()

    invoice_reference = factory_invoice_reference(invoice_id=invoice.id, invoice_number=payment.invoice_number)
    invoice_reference.save()
    non_sufficient_funds = factory_non_sufficient_funds(
        invoice_id=invoice.id, invoice_number=payment.invoice_number, description="EFT invoice overdue"
    )
    non_sufficient_funds.save()
    s1_settings = factory_statement_settings(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
    ).save()
    statement = factory_statement(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=s1_settings.id,
    ).save()
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id).save()

    find_non_sufficient_funds = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(
        account_id=payment_account.auth_account_id
    )

    assert find_non_sufficient_funds is not None
    assert "statements" in find_non_sufficient_funds
    assert "invoices" in find_non_sufficient_funds
    assert "total_amount" in find_non_sufficient_funds
    assert "total_amount_remaining" in find_non_sufficient_funds
    assert "nsf_amount" in find_non_sufficient_funds
    assert "total" in find_non_sufficient_funds
    assert len(find_non_sufficient_funds["invoices"]) == 1
    assert len(find_non_sufficient_funds["statements"]) == 1
    assert find_non_sufficient_funds["total"] == 1
    assert find_non_sufficient_funds["total_amount"] == 0
    assert find_non_sufficient_funds["total_amount_remaining"] == 30.0
    assert find_non_sufficient_funds["nsf_amount"] == 30.0
    assert find_non_sufficient_funds["reason"] == "EFT invoice overdue"


def _create_invoice_with_nsf_row(status_code: str, total: int, paid: int):
    """Generate test NSF and account data."""
    invoice_number = "REG00000001"
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account=payment_account, status_code=status_code, paid=paid, total=total)
    invoice.save()
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    factory_payment_line_item(
        invoice_id=invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        description="Annual Report",
        total=total,
        filing_fees=0,
    ).save()
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number).save()
    factory_non_sufficient_funds(invoice_id=invoice.id, invoice_number=invoice_number, description="NSF").save()
    settings = factory_statement_settings(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
    ).save()
    statement = factory_statement(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings.id,
    ).save()
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id).save()
    return payment_account


@pytest.mark.parametrize(
    "status_code, paid, expected_remaining",
    [
        (InvoiceStatus.CREATED.value, 0, 30.0),
        (InvoiceStatus.SETTLEMENT_SCHEDULED.value, 0, 30.0),
        (InvoiceStatus.PARTIAL.value, 10, 20.0),
        (InvoiceStatus.OVERDUE.value, 0, 30.0),
        (InvoiceStatus.APPROVED.value, 0, 30.0),
    ],
)
def test_find_all_non_sufficient_funds_invoices_includes_outstanding(session, status_code, paid, expected_remaining):
    """Assert invoices NSF outstanding balance statuses are included."""
    payment_account = _create_invoice_with_nsf_row(status_code, total=30, paid=paid)

    result = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(
        account_id=payment_account.auth_account_id
    )

    assert result["total"] == 1
    assert len(result["invoices"]) == 1
    assert len(result["statements"]) == 1
    assert result["total_amount_remaining"] == expected_remaining
    assert result["reason"] == "NSF"


@pytest.mark.parametrize(
    "status_code, paid",
    [
        (InvoiceStatus.PAID.value, 30),
        (InvoiceStatus.CREDITED.value, 30),
        (InvoiceStatus.CREDITED.value, 0),
        (InvoiceStatus.CANCELLED.value, 0),
        (InvoiceStatus.DELETED.value, 0),
        (InvoiceStatus.REFUND_REQUESTED.value, 30),
        (InvoiceStatus.REFUNDED.value, 30),
    ],
)
def test_find_all_non_sufficient_funds_invoices_excludes_not_outstanding(session, status_code, paid):
    """Assert invoices statuses that are not outstanding with and NSF row do not appear."""
    payment_account = _create_invoice_with_nsf_row(status_code, total=30, paid=paid)

    result = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(
        account_id=payment_account.auth_account_id
    )

    assert result["total"] == 0
    assert result["invoices"] == []
    assert result["statements"] == []
    assert result["total_amount"] == 0
    assert result["total_amount_remaining"] == 0
    assert result["nsf_amount"] == 0
    assert result["reason"] == "None"
