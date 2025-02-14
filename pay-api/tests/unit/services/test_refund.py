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

"""Tests to assure the Refund Service.

Test-Suite to ensure that the Refund Service is working as expected.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.services import RefundService
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, TransactionStatus
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_transaction,
    factory_receipt,
)


def test_create_refund_for_unpaid_invoice(session):
    """Assert that the create refund fails for unpaid invoices."""
    payment_account = factory_payment_account()
    payment_account.save()

    i = factory_invoice(payment_account=payment_account)
    i.save()
    factory_invoice_reference(i.id).save()

    with pytest.raises(Exception) as excinfo:
        RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"})
    assert excinfo.type == BusinessException


@pytest.mark.disable_mock_pub_sub_call
@pytest.mark.parametrize(
    "payment_method, invoice_status, pay_status, has_reference, expected_inv_status",
    [
        (
            PaymentMethod.PAD.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.CREDITED.value,
        ),
        (
            PaymentMethod.PAD.value,
            InvoiceStatus.APPROVED.value,
            None,
            False,
            InvoiceStatus.CANCELLED.value,
        ),
        (
            PaymentMethod.ONLINE_BANKING.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.CREDITED.value,
        ),
        (
            PaymentMethod.DRAWDOWN.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.REFUND_REQUESTED.value,
        ),
        (
            PaymentMethod.DIRECT_PAY.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.REFUND_REQUESTED.value,
        ),
        (
            PaymentMethod.CC.value,
            InvoiceStatus.PAID.value,
            PaymentStatus.COMPLETED.value,
            True,
            InvoiceStatus.CREDITED.value,
        ),
    ],
)
@patch("google.cloud.pubsub_v1.PublisherClient.publish")
def test_create_refund_for_paid_invoice(
    mock_publish, session, monkeypatch, payment_method, invoice_status, pay_status, has_reference, expected_inv_status
):
    """Assert that the create refund succeeds for paid invoices."""
    expected = REFUND_SUCCESS_MESSAGES[f"{payment_method}.{invoice_status}"]
    payment_account = factory_payment_account(payment_method_code=payment_method)
    payment_account.save()

    i = factory_invoice(payment_account=payment_account, payment_method_code=payment_method)
    i.save()
    if has_reference:
        inv_ref = factory_invoice_reference(i.id)
        inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
        inv_ref.save()

        payment = factory_payment(invoice_number=inv_ref.invoice_number, payment_status_code=pay_status).save()

        factory_payment_transaction(payment_id=payment.id, status_code=TransactionStatus.COMPLETED.value).save()

    i.invoice_status_code = invoice_status
    i.save()

    factory_receipt(invoice_id=i.id, receipt_number="1234569546456").save()

    message = RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"})
    i = InvoiceModel.find_by_id(i.id)

    assert i.invoice_status_code == expected_inv_status
    assert message["message"] == expected
    if i.invoice_status_code in (
        InvoiceStatus.CANCELLED.value,
        InvoiceStatus.CREDITED.value,
        InvoiceStatus.REFUNDED.value,
    ):
        assert i.refund_date
        mock_publish.assert_called()


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
    i.payment_date = datetime.now(tz=timezone.utc)
    i.save()

    factory_receipt(invoice_id=i.id, receipt_number="953959345343").save()

    RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"})
    i = InvoiceModel.find_by_id(i.id)
    payment: PaymentModel = PaymentModel.find_by_id(payment.id)

    assert i.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

    with pytest.raises(Exception) as excinfo:
        RefundService.create_refund(invoice_id=i.id, request={"reason": "Test"})
    assert excinfo.type == BusinessException
