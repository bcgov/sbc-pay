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

"""Tests to assure the FeeSchedule Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""

from datetime import datetime

from pay_api.models import FeeSchedule, Invoice, Payment, PaymentAccount, PaymentLineItem
from pay_api.services.payment_line_item import PaymentLineItem as PaymentLineService
from pay_api.utils.enums import Status

def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code=Status.DRAFT.value):
    """Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str):
    """Factory."""
    return Invoice(payment_id=payment_id,
                   invoice_status_code=Status.DRAFT.value,
                   account_id=account_id,
                   total=0, created_by='test', created_on=datetime.now())


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10):
    """Factory."""
    return PaymentLineItem(invoice_id=invoice_id,
                           fee_schedule_id=fee_schedule_id,
                           filing_fees=filing_fees,
                           total=total,
                           line_item_status_code='CREATED')


def test_line_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    p = PaymentLineService.find_by_id(line.id)

    assert p is not None
    assert p.id is not None
    assert p.invoice_id is not None
    assert p.filing_fees is not None
    assert p.fee_schedule_id is not None
    assert p.processing_fees is None
    assert p.service_fees is None
    assert p.gst is None
    assert p.pst is None


def test_line_invalid_lookup(session):
    """Test Invalid lookup."""
    p = PaymentLineService.find_by_id(999)

    assert p is not None
    assert p.id is None
