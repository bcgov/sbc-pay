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

from datetime import datetime, timezone

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.services.receipt import Receipt as ReceiptService
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account, factory_payment_line_item,
    get_paybc_transaction_request)


def test_receipt_saved_from_new(session):
    """Assert that the receipt is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()
    factory_invoice_reference(i.id).save()

    receipt_service = ReceiptService()
    receipt_service.receipt_number = '1234567890'
    receipt_service.invoice_id = i.id
    receipt_service.receipt_date = datetime.now(tz=timezone.utc)
    receipt_service.receipt_amount = 100
    receipt_service = receipt_service.save()

    receipt_service = ReceiptService.find_by_id(receipt_service.id)

    assert receipt_service is not None
    assert receipt_service.id is not None
    assert receipt_service.receipt_date is not None
    assert receipt_service.invoice_id is not None

    receipt_service = ReceiptService.find_by_invoice_id_and_receipt_number(i.id, receipt_service.receipt_number)

    assert receipt_service is not None
    assert receipt_service.id is not None


def test_receipt_invalid_lookup(session):
    """Test invalid lookup."""
    receipt = ReceiptService.find_by_id(999)

    assert receipt is not None
    assert receipt.id is None

    receipt = ReceiptService.find_by_invoice_id_and_receipt_number(999, '1234567890')

    assert receipt is not None
    assert receipt.id is None


def test_create_receipt_with_invoice(session, public_user_mock):
    """Try creating a receipt with invoice number."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(payment_account, total=50)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    payment = factory_payment(invoice_amount=50)
    payment.save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    PaymentTransactionService.update_transaction(transaction.id, '')

    input_data = {
        'corpName': 'Pennsular Coop ',
        'filingDateTime': '1999',
        'fileName': 'coopser'
    }

    response = ReceiptService.create_receipt(invoice.id, input_data, skip_auth_check=True)
    assert response is not None


def test_create_receipt_with_no_receipt(session, public_user_mock):
    """Try creating a receipt with invoice number."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    input_data = {
        'corpName': 'Pennsular Coop ',
        'filingDateTime': '1999',
        'fileName': 'coopser'
    }

    with pytest.raises(BusinessException) as excinfo:
        ReceiptService.create_receipt(invoice.id, input_data, skip_auth_check=True)
    assert excinfo.type == BusinessException
