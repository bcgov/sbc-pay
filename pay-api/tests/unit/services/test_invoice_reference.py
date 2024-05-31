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

"""Tests to assure the Invoice Reference.

Test-Suite to ensure that the Invoice Reference Service is working as expected.
"""

from pay_api.services.invoice_reference import InvoiceReference
from pay_api.utils.enums import InvoiceReferenceStatus
from tests.utilities.base_test import factory_invoice, factory_payment, factory_payment_account


def test_invoice_saved_from_new(session):
    """Assert that the invoice reference is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()

    invoice_reference = InvoiceReference.create(i.id, 'TEST_INV_NUMBER', 'TEST_REF_NUMBER')

    assert invoice_reference is not None
    assert invoice_reference.id is not None
    assert invoice_reference.invoice_id == i.id
    assert invoice_reference.status_code == InvoiceReferenceStatus.ACTIVE.value


def test_invoice_invalid_lookup(session):
    """Test invalid lookup."""
    inv_reference = InvoiceReference.find_active_reference_by_invoice_id(999)
    assert inv_reference is None


def test_active_reference_by_invoice_id(session):
    """Assert that the invoice reference lookup is working."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()

    InvoiceReference.create(i.id, 'TEST_INV_NUMBER', 'TEST_REF_NUMBER')

    # Do a look up
    invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(i.id)

    assert invoice_reference is not None
    assert invoice_reference.id is not None
    assert invoice_reference.invoice_id == i.id


def test_find_completed_reference_by_invoice_id(session):
    """Assert that the completed invoice reference lookup is working."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()

    invoice_reference = InvoiceReference.create(i.id, 'TEST_INV_NUMBER', 'TEST_REF_NUMBER')
    invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
    invoice_reference.save()

    # Do a look up
    invoice_reference = InvoiceReference.find_completed_reference_by_invoice_id(i.id)

    assert invoice_reference is not None
    assert invoice_reference.id is not None
    assert invoice_reference.invoice_id == i.id
