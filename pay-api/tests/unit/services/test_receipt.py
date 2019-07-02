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

"""Tests to assure the Receipt Service.

Test-Suite to ensure that the Receipt Service is working as expected.
"""

from datetime import datetime

from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.services.payment_service import PaymentService
from pay_api.services.receipt import Receipt as ReceiptService
from pay_api.utils.enums import Status


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(
        corp_number=corp_number,
        corp_type_code=corp_type_code,
        payment_system_code=payment_system_code,
        party_number='11111',
        account_number='4101',
        site_number='29921',
    )


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='DRAFT'):
    """Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str):
    """Factory."""
    return Invoice(payment_id=payment_id,
                   invoice_status_code='DRAFT',
                   account_id=account_id,
                   total=0, created_by='test', created_on=datetime.now(), invoice_number='10021')


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10):
    """Factory."""
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        line_item_status_code=Status.CREATED.value,
    )


def factory_payment_transaction(
        payment_id: str,
        status_code: str = Status.DRAFT.value,
        client_system_url: str = 'http://google.com/',
        pay_system_url: str = 'http://google.com',
        transaction_start_time: datetime = datetime.now(),
        transaction_end_time: datetime = datetime.now(),
):
    """Factory."""
    return PaymentTransaction(
        payment_id=payment_id,
        status_code=status_code,
        client_system_url=client_system_url,
        pay_system_url=pay_system_url,
        transaction_start_time=transaction_start_time,
        transaction_end_time=transaction_end_time,
    )


def test_receipt_saved_from_new(session):
    """Assert that the receipt is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    i.save()
    receipt_service = ReceiptService()
    receipt_service.receipt_number = '1234567890'
    receipt_service.invoice_id = i.id
    receipt_service.receipt_date = datetime.now()
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


def test_create_receipt_without_invoice(session):
    """Try creating a receipt without invoice number."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
    }

    PaymentService.update_payment(payment.id, payment_request, 'test')
    input_data = {
        'corpName': 'Pennsular Coop ',
        'filingDateTime': '1999',
        'fileName': 'coopser'
    }
    response = ReceiptService.create_receipt(payment.id, '', input_data)
    assert response is not None


def test_create_receipt_with_invoice(session):
    """Try creating a receipt with invoice number."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    transaction = factory_payment_transaction(payment.id)
    transaction.save()

    payment_request = {
        'payment_info': {'method_of_payment': 'CC'},
        'business_info': {
            'business_identifier': 'CP1234',
            'corp_type': 'CP',
            'business_name': 'ABC Corp',
            'contact_info': {
                'city': 'Victoria',
                'postal_code': 'V8P2P2',
                'province': 'BC',
                'address_line_1': '100 Douglas Street',
                'country': 'CA',
            },
        },
        'filing_info': {
            'filing_types': [{'filing_type_code': 'OTADD', 'filing_description': 'TEST'}, {'filing_type_code': 'OTANN'}]
        },
    }

    PaymentService.update_payment(payment.id, payment_request, 'test')
    input_data = {
        'corpName': 'Pennsular Coop ',
        'filingDateTime': '1999',
        'fileName': 'coopser'
    }
    response = ReceiptService.create_receipt(payment.id, invoice.id, input_data)
    assert response is not None
