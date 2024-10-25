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

import pytest
from freezegun import freeze_time
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentStatus, RefundsPartialType

from tasks.common.enums import PaymentDetailsGlStatus
from tasks.direct_pay_automated_refund_task import DirectPayAutomatedRefundTask

from .factory import (
    factory_create_direct_pay_account,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_line_item,
    factory_refund_invoice,
    factory_refund_partial,
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


def test_complete_refund_partial(session, monkeypatch):
    """Test partial refund GL complete."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.PAID.value)
    invoice.refund_date = datetime.datetime.now(tz=datetime.timezone.utc)
    invoice.save()
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value).save()
    payment = factory_payment("PAYBC", invoice_number=invoice.id, payment_status_code=PaymentStatus.COMPLETED.value)
    factory_refund_invoice(invoice.id)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_refund_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line.id,
        refund_amount=line.filing_fees - 1,
        created_by="test",
        refund_type=RefundsPartialType.BASE_FEES.value,
    )

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
        assert invoice.invoice_status_code == InvoiceStatus.PAID.value
        assert invoice.refund_date is not None
        assert payment.payment_status_code == PaymentStatus.COMPLETED.value
        assert refund.gl_posted is not None

        refunds_partials = session.query(RefundsPartialModel).filter(RefundsPartialModel.invoice_id == invoice.id).all()
        assert refunds_partials
        assert refunds_partials[0].gl_posted is not None


@pytest.mark.parametrize(
    "gl_error_code, gl_error_message",
    [
        (PaymentDetailsGlStatus.RJCT.value, "REJECTED"),
        (PaymentDetailsGlStatus.DECLINED.value, "DECLINED"),
    ],
)
def test_error_refund_partial(session, monkeypatch, gl_error_code, gl_error_message):
    """Test partial refund GL error."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.PAID.value)
    invoice.refund_date = datetime.datetime.now(tz=datetime.timezone.utc)
    invoice.save()
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value).save()
    payment = factory_payment("PAYBC", invoice_number=invoice.id, payment_status_code=PaymentStatus.COMPLETED.value)
    factory_refund_invoice(invoice.id)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_refund_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line.id,
        refund_amount=line.filing_fees - 1,
        created_by="test",
        refund_type=RefundsPartialType.BASE_FEES.value,
    )

    def payment_status(
        cls,
    ):  # pylint: disable=unused-argument; mocks of library methods
        return {
            "revenue": [{"refund_data": [{"refundglstatus": gl_error_code, "refundglerrormessage": gl_error_message}]}]
        }

    target = "tasks.direct_pay_automated_refund_task.DirectPayAutomatedRefundTask._query_order_status"
    monkeypatch.setattr(target, payment_status)

    with freeze_time(
        datetime.datetime.combine(datetime.datetime.now(tz=datetime.timezone.utc).date(), datetime.time(6, 00))
    ):
        DirectPayAutomatedRefundTask().process_cc_refunds()
        refund = RefundModel.find_by_invoice_id(invoice.id)
        assert invoice.invoice_status_code == InvoiceStatus.PAID.value
        assert invoice.refund_date is not None
        assert payment.payment_status_code == PaymentStatus.COMPLETED.value
        assert refund.gl_posted is None
        assert refund.gl_error == gl_error_message

        refunds_partials = session.query(RefundsPartialModel).filter(RefundsPartialModel.invoice_id == invoice.id).all()
        assert refunds_partials
        assert refunds_partials[0].gl_posted is None
