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
from pay_api.models import CorpType, FeeCode, FeeSchedule, FilingType
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.services.receipt import Receipt as ReceiptService
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
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
    corp_type = CorpType(code="CP", description="Cooperative")
    corp_type.save()
    fee_code = FeeCode(code="NOCOI_FEE", amount=25.00)
    fee_code.save()
    fee_schedule = FeeScheduleModel(filing_type_code="NOCOI", corp_type_code="CP", fee_code="NOCOI_FEE")
    fee_schedule.save()

    # Create payment line item with NOCOI filing type
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    filing_data = {"corpName": "Test Corp"}
    receipt_details = ReceiptService.get_receipt_details(filing_data, invoice.id, skip_auth_check=True)
    assert receipt_details["isSubmission"] is True
