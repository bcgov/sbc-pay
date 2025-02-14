# Copyright © 2022 Province of British Columbia
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

"""Tests to assure the BCOL Refund Confirmation Job."""
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from pay_api.models import Invoice
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, PaymentSystem

from tasks.bcol_refund_confirmation_task import BcolRefundConfirmationTask

from .factory import (
    factory_create_direct_pay_account,
    factory_create_pad_account,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
)


@pytest.mark.parametrize(
    "test_name, payment_method, invoice_total, refund_total, start_status, expected, mismatch",
    [
        (
            "drawdown_refund_full",
            PaymentMethod.DRAWDOWN.value,
            31.5,
            -31.5,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.REFUNDED.value,
            False,
        ),
        (
            "drawdown_refund_partial",
            PaymentMethod.DRAWDOWN.value,
            31.5,
            -10,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            True,
        ),
        (
            "drawdown_refund_none",
            PaymentMethod.DRAWDOWN.value,
            31.5,
            0,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            False,
        ),
        (
            "no_refund_requested",
            PaymentMethod.DRAWDOWN.value,
            31.5,
            -31.5,
            InvoiceStatus.APPROVED.value,
            InvoiceStatus.APPROVED.value,
            False,
        ),
    ],
)
def test_bcol_refund_confirmation(
    session,
    monkeypatch,
    test_name,
    payment_method,
    invoice_total,
    refund_total,
    start_status,
    expected,
    mismatch,
):
    """Test bcol refund confirmation."""
    invoice_number = f"{test_name}000012345"
    # setup mocks

    colin_bcol_records_mock = Mock(return_value=({invoice_number: Decimal(refund_total)} if refund_total != 0 else {}))
    sentry_mock = Mock()

    monkeypatch.setattr(
        "tasks.bcol_refund_confirmation_task.BcolRefundConfirmationTask._get_data_warehouse_bcol_records_for_invoices",
        colin_bcol_records_mock,
    )
    monkeypatch.setattr("tasks.bcol_refund_confirmation_task.capture_message", sentry_mock)
    # setup invoice / invoice reference / payment
    pay_account = None
    if payment_method == PaymentMethod.PAD.value:
        pay_account = factory_create_pad_account(
            status=CfsAccountStatus.ACTIVE.value, payment_method=PaymentMethod.PAD.value
        )
    else:
        pay_account = factory_create_direct_pay_account(payment_method=PaymentMethod.DRAWDOWN.value)

    invoice = factory_invoice(
        payment_account=pay_account,
        payment_method_code=pay_account.payment_method,
        status_code=InvoiceStatus.REFUND_REQUESTED.value,
        total=invoice_total,
    )
    # explicitly set status to starting value (factory method overwrites it for pad)
    invoice.invoice_status_code = start_status
    invoice.save()

    inv_ref = factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    factory_payment(
        invoice_number=inv_ref.invoice_number,
        payment_status_code="COMPLETED",
        payment_system_code=PaymentSystem.BCOL.value,
    )

    with patch("google.cloud.pubsub_v1.PublisherClient") as publisher:
        BcolRefundConfirmationTask.update_bcol_refund_invoices()
        if test_name == "drawdown_refund_full":
            publisher.assert_called_once()

    # check things out
    assert (Invoice.find_by_id(invoice.id)).invoice_status_code == expected
    if mismatch:
        sentry_mock.assert_called_once()
    else:
        sentry_mock.assert_not_called()
