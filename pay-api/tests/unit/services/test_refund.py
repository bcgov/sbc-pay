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

"""Tests to assure the Refund Service.

Test-Suite to ensure that the Refund Service is working as expected.
"""

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import Invoice as InvoiceModel, Payment as PaymentModel
from pay_api.services import RefundService
from pay_api.utils.enums import InvoiceStatus, PaymentStatus, TransactionStatus, InvoiceReferenceStatus
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account, factory_payment_transaction,
    factory_receipt)


def test_create_refund_for_unpaid_invoice(session):
    """Assert that the create refund fails for unpaid invoices."""
    payment_account = factory_payment_account()
    payment_account.save()

    i = factory_invoice(payment_account=payment_account)
    i.save()
    factory_invoice_reference(i.id).save()

    with pytest.raises(Exception) as excinfo:
        RefundService.create_refund(invoice_id=i.id, request={'reason': 'Test'})
    assert excinfo.type == BusinessException


def test_create_refund_for_paid_invoice(session, monkeypatch):
    """Assert that the create refund succeeds for paid invoices."""
    payment_account = factory_payment_account()
    payment_account.save()

    i = factory_invoice(payment_account=payment_account)
    i.save()
    inv_ref = factory_invoice_reference(i.id)
    inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
    inv_ref.save()

    payment = factory_payment(invoice_number=inv_ref.invoice_number).save()

    factory_payment_transaction(payment_id=payment.id, status_code=TransactionStatus.COMPLETED.value).save()

    i.invoice_status_code = InvoiceStatus.PAID.value
    i.save()

    factory_receipt(invoice_id=i.id).save()

    monkeypatch.setattr('pay_api.services.refund.publish_response', lambda *args, **kwargs: None)

    RefundService.create_refund(invoice_id=i.id, request={'reason': 'Test'})
    i = InvoiceModel.find_by_id(i.id)
    payment: PaymentModel = PaymentModel.find_by_id(payment.id)

    assert i.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
    assert payment.payment_status_code == PaymentStatus.REFUNDED.value


def test_create_duplicate_refund_for_paid_invoice(session, monkeypatch):
    """Assert that the create duplicate refund fails for paid invoices."""
    payment_account = factory_payment_account()
    payment_account.save()

    i = factory_invoice(payment_account=payment_account)
    i.save()
    inv_ref = factory_invoice_reference(i.id)
    inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
    inv_ref.save()

    payment = factory_payment(invoice_number=inv_ref.invoice_number).save()

    factory_payment_transaction(payment_id=payment.id, status_code=TransactionStatus.COMPLETED.value).save()

    i.invoice_status_code = InvoiceStatus.PAID.value
    i.save()

    factory_receipt(invoice_id=i.id).save()
    monkeypatch.setattr('pay_api.services.refund.publish_response', lambda *args, **kwargs: None)

    RefundService.create_refund(invoice_id=i.id, request={'reason': 'Test'})
    i = InvoiceModel.find_by_id(i.id)
    payment: PaymentModel = PaymentModel.find_by_id(payment.id)

    assert i.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
    assert payment.payment_status_code == PaymentStatus.REFUNDED.value

    with pytest.raises(Exception) as excinfo:
        RefundService.create_refund(invoice_id=i.id, request={'reason': 'Test'})
    assert excinfo.type == BusinessException
