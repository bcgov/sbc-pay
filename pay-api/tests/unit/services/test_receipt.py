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

"""Tests to assure the Receipt Service.

Test-Suite to ensure that the Receipt Service is working as expected.
"""

from datetime import UTC, datetime

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import FeeCode, FeeSchedule, FilingType
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.services.receipt import Receipt as ReceiptService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from pay_api.utils.util import get_local_formatted_date
from tests.utilities.base_test import (
    factory_applied_credits,
    factory_credit,
    factory_distribution_code,
    factory_distribution_link,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_refunds_partial,
    get_paybc_transaction_request,
)


def test_receipt_saved_from_new(session):
    """Assert that the receipt is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()
    factory_invoice_reference(i.id).save()

    receipt = ReceiptModel()
    receipt.receipt_number = "1234567890"
    receipt.invoice_id = i.id
    receipt.receipt_date = datetime.now(tz=UTC)
    receipt.receipt_amount = 100
    receipt = receipt.save()

    rm_lookup = ReceiptModel.find_by_id(receipt.id)

    assert rm_lookup is not None
    assert rm_lookup.id is not None
    assert rm_lookup.receipt_date is not None
    assert rm_lookup.invoice_id is not None

    rm_lookup = ReceiptService.find_by_invoice_id_and_receipt_number(i.id, rm_lookup.receipt_number)

    assert rm_lookup is not None
    assert rm_lookup.id is not None


def test_receipt_invalid_lookup(session):
    """Test invalid lookup."""
    receipt = ReceiptModel.find_by_id(999)

    assert receipt is None
    receipt = ReceiptService.find_by_invoice_id_and_receipt_number(999, "1234567890")
    assert receipt is None


def test_create_receipt_with_invoice(session, public_user_mock):
    """Try creating a receipt with invoice number."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(payment_account, total=50)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    payment = factory_payment(invoice_amount=50)
    payment.save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    PaymentTransactionService.update_transaction(transaction.id, "")

    input_data = {
        "corpName": "Pennsular Coop ",
        "filingDateTime": "1999",
        "fileName": "coopser",
    }

    response = ReceiptService.create_receipt(invoice.id, input_data, skip_auth_check=True)
    assert response is not None

    receipt_details = ReceiptService.get_receipt_details(input_data, invoice.id, skip_auth_check=True)
    assert receipt_details["isSubmission"] is False


def test_create_receipt_with_no_receipt(session, public_user_mock):
    """Try creating a receipt with invoice number."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    input_data = {
        "corpName": "Pennsular Coop ",
        "filingDateTime": "1999",
        "fileName": "coopser",
    }

    with pytest.raises(BusinessException) as excinfo:
        ReceiptService.create_receipt(invoice.id, input_data, skip_auth_check=True)
    assert excinfo.type == BusinessException


def test_receipt_details_is_submission_true_with_nocoi(session):
    """Test isSubmission is True when NOCOI filing type exists."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    filing_type = FilingType(code="NOCOI", description="No COI Filing")
    filing_type.save()
    fee_code = FeeCode(code="NOCOI_FEE", amount=25.00)
    fee_code.save()
    # NOCOI is a filing type that's specific for officers it's free so it's considered a submission
    fee_schedule = FeeScheduleModel(filing_type_code="NOCOI", corp_type_code="CP", fee_code="NOCOI_FEE")
    fee_schedule.save()

    distribution_code = factory_distribution_code("Test Distribution Code")
    distribution_code.save()
    distribution_link = factory_distribution_link(distribution_code.distribution_code_id, fee_schedule.fee_schedule_id)
    distribution_link.save()

    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    receipt = ReceiptModel()
    receipt.receipt_number = "1234567890"
    receipt.invoice_id = invoice.id
    receipt.receipt_date = datetime.now(tz=UTC)
    receipt.receipt_amount = 25.00
    receipt.save()

    filing_data = {"corpName": "Test Corp"}
    receipt_details = ReceiptService.get_receipt_details(filing_data, invoice.id, skip_auth_check=True)
    assert receipt_details["isSubmission"] is True


def test_receipt_with_pad_invoice_applied_credits_and_partial_refund(session):
    """Test receipt with PAD invoice, applied credits, and partial refund."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.PAD.value)
    payment_account.save()

    invoice = factory_invoice(
        payment_account,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.PAD.value,
        total=100,
        refund=25,
    )
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, total=100)
    line.save()

    receipt = ReceiptModel()
    receipt.receipt_number = "1234567890"
    receipt.invoice_id = invoice.id
    receipt.receipt_date = datetime.now(tz=UTC)
    receipt.receipt_amount = 100.00
    receipt.save()

    credit = factory_credit(account_id=payment_account.id, amount=50.00, remaining_amount=25.00)
    factory_applied_credits(invoice_id=invoice.id, credit_id=credit.id, amount_applied=25.00)
    factory_refunds_partial(invoice_id=invoice.id, payment_line_item_id=line.id, refund_amount=25.00)

    filing_data = {"corpName": "Test Corp", "isRefund": True}
    receipt_details = ReceiptService.get_receipt_details(filing_data, invoice.id, skip_auth_check=True)
    assert receipt_details is not None
    assert "partialRefund" in receipt_details


@pytest.mark.parametrize(
    "filing_data,payment_method_code,use_refund_date,use_created_on",
    [
        (True, PaymentMethod.CC.value, True, False),
        (False, PaymentMethod.PAD.value, False, True),
        (False, PaymentMethod.EJV.value, False, True),
        (False, PaymentMethod.EFT.value, False, True),
        (False, PaymentMethod.CC.value, False, False),
    ],
)
def test_get_receipt_date(session, is_refund, payment_method_code, use_refund_date, use_created_on):
    payment_account = factory_payment_account()
    payment_account.save()

    refund_date = datetime(2024, 1, 2, tzinfo=UTC)
    created_on = datetime(2024, 2, 3, tzinfo=UTC)
    payment_date = datetime(2024, 3, 4, tzinfo=UTC)

    invoice = factory_invoice(
        payment_account,
        payment_method_code=payment_method_code,
        created_on=created_on,
        payment_date=payment_date,
        refund_date=refund_date if use_refund_date else None,
    )

    result = ReceiptService.get_receipt_date(is_refund, invoice)

    if use_refund_date:
        expected_raw = refund_date
    elif use_created_on:
        expected_raw = created_on
    else:
        expected_raw = payment_date

    assert result == get_local_formatted_date(expected_raw)
