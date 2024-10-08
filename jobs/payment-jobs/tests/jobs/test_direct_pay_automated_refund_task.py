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

"""Tests for direct pay automated refund task."""
import datetime

from freezegun import freeze_time
from pay_api.models import Refund as RefundModel
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentStatus

from tasks.direct_pay_automated_refund_task import DirectPayAutomatedRefundTask

from .factory import (
    factory_create_direct_pay_account,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_refund_invoice,
)


def test_automated_refund_task(session):
    """Test automated refund task, runs without exceptions."""
    DirectPayAutomatedRefundTask().process_cc_refunds()
    assert True


def test_successful_paid_refund(session, monkeypatch):
    """Bambora paid, but not GL complete."""
    payment_account = factory_create_direct_pay_account()
    invoice = factory_invoice(
        payment_account=payment_account,
        status_code=InvoiceStatus.REFUND_REQUESTED.value,
    )
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value).save()
    payment = factory_payment("PAYBC", invoice_number=invoice.id)
    refund = factory_refund_invoice(invoice.id)

    def payment_status(
        cls,
    ):  # pylint: disable=unused-argument; mocks of library methods
        return {"revenue": [{"refund_data": [{"refundglstatus": "PAID", "refundglerrormessage": ""}]}]}

    target = "tasks.direct_pay_automated_refund_task.DirectPayAutomatedRefundTask._query_order_status"
    monkeypatch.setattr(target, payment_status)

    DirectPayAutomatedRefundTask().process_cc_refunds()
    assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value
    assert invoice.refund_date is not None
    assert payment.payment_status_code == PaymentStatus.REFUNDED.value
    assert refund.gl_posted is None


def test_successful_completed_refund(session, monkeypatch):
    """Test successful refund (GL complete)."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.REFUNDED.value)
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value).save()
    payment = factory_payment("PAYBC", invoice_number=invoice.id)
    refund = factory_refund_invoice(invoice.id)

    def payment_status(
        cls,
    ):  # pylint: disable=unused-argument; mocks of library methods
        return {"revenue": [{"refund_data": [{"refundglstatus": "CMPLT", "refundglerrormessage": ""}]}]}

    target = "tasks.direct_pay_automated_refund_task.DirectPayAutomatedRefundTask._query_order_status"
    monkeypatch.setattr(target, payment_status)

    with freeze_time(
        datetime.datetime.combine(datetime.datetime.now(tz=datetime.timezone.utc).date(), datetime.time(6, 00))
    ):
        DirectPayAutomatedRefundTask().process_cc_refunds()
        refund = RefundModel.find_by_invoice_id(invoice.id)
        assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value
        assert invoice.refund_date is not None
        assert payment.payment_status_code == PaymentStatus.REFUNDED.value
        assert refund.gl_posted is not None


def test_bad_cfs_refund(session, monkeypatch):
    """Test RJCT refund."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.REFUNDED.value)
    refund = factory_refund_invoice(invoice.id)
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value).save()

    def payment_status(
        cls,
    ):  # pylint: disable=unused-argument; mocks of library methods
        return {
            "revenue": [
                {
                    "linenumber": "1",
                    "revenueaccount": "112.32041.35301.1278.3200000.000000.0000",
                    "revenueamount": "130",
                    "glstatus": "PAID",
                    "glerrormessage": None,
                    "refund_data": [{"refundglstatus": "RJCT", "refundglerrormessage": "BAD"}],
                },
                {
                    "linenumber": "2",
                    "revenueaccount": "112.32041.35301.1278.3200000.000000.0000",
                    "revenueamount": "1.5",
                    "glstatus": "PAID",
                    "glerrormessage": None,
                    "refund_data": [{"refundglstatus": "RJCT", "refundglerrormessage": "BAD"}],
                },
            ]
        }

    target = "tasks.direct_pay_automated_refund_task.DirectPayAutomatedRefundTask._query_order_status"
    monkeypatch.setattr(target, payment_status)

    with freeze_time(
        datetime.datetime.combine(datetime.datetime.now(tz=datetime.timezone.utc).date(), datetime.time(6, 00))
    ):
        DirectPayAutomatedRefundTask().process_cc_refunds()
        assert refund.gl_error == "BAD BAD"
        assert refund.gl_posted is None
