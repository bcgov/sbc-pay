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

from pay_api.services.payment import Payment as Payment_service
from pay_api.utils.enums import Status
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account)


def test_payment_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment.id, payment_account.id)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = Payment_service.find_by_id(payment.id, skip_auth_check=True)

    assert p is not None
    assert p.id is not None
    assert p.payment_system_code is not None
    assert p.payment_method_code is not None
    assert p.payment_status_code is not None
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
    invoice = factory_invoice(payment.id, payment_account.id, Status.DELETED.value)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = Payment_service.find_by_id(payment.id, skip_auth_check=True)

    assert p is not None
    assert p.id is not None
