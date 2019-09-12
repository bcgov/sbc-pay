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
from pay_api.services.payment import Payment as Payment_service
from pay_api.utils.enums import Status


def factory_payment_account(corp_number: str = 'CP0001234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC',
                    payment_status_code=Status.DRAFT.value):
    """Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str, invoice_status_code: str = Status.DRAFT.value):
    """Factory."""
    return Invoice(
        payment_id=payment_id,
        invoice_status_code=invoice_status_code,
        account_id=account_id,
        total=0,
        created_by='test',
        created_on=datetime.now(),
    )


def test_payment_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    p = Payment_service.find_by_id(payment.id, skip_auth_check=True)

    assert p is not None
    assert p.id is not None
    assert p.payment_system_code is not None
    assert p.payment_method_code is not None
    assert p.payment_status_code is not None
    assert p.created_by is not None
    assert p.created_on is not None
    assert p.updated_on is None
    assert p.updated_by is None
    assert p.invoices is not None


def test_payment_invalid_lookup(session):
    """Test invalid lookup."""
    p = Payment_service.find_by_id(999, skip_auth_check=True)

    assert p is not None
    assert p.id is None


def test_payment_with_no_active_invoice(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id, Status.CANCELLED.value)
    invoice.save()
    p = Payment_service.find_by_id(payment.id, skip_auth_check=True)

    assert p is not None
    assert p.id is not None

    json = p.asdict()
    assert json.get('invoices', None) is None
