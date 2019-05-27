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

from pay_api.models import Invoice, Payment, PaymentAccount
from pay_api.services.invoice import Invoice as Invoice_service


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='DRAFT',
                    total: int = 0):
    """Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, total=total, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str):
    """Factory."""
    return Invoice(payment_id=payment_id,
                   invoice_status_code='DRAFT',
                   account_id=account_id,
                   total=0, created_by='test', created_on=datetime.now())


def test_invoice_saved_from_new(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    i.save()

    invoice = Invoice_service.find_by_id(i.id)

    assert invoice is not None
    assert invoice.id is not None
    assert invoice.payment_id is not None
    assert invoice.invoice_number is None
    assert invoice.reference_number is None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is None
    assert invoice.created_on is not None
    assert invoice.created_by is not None
    assert invoice.updated_by is None
    assert invoice.updated_on is None
    assert invoice.account_id is not None


def test_invoice_invalid_lookup(session):
    """Test invalid lookup."""
    invoice = Invoice_service.find_by_id(999)

    assert invoice is not None
    assert invoice.id is None
