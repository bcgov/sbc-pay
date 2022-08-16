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

"""Tests for cfs cc automated refund."""
from pay_api.utils.enums import (
    DisbursementStatus, InvoiceReferenceStatus, InvoiceStatus,
    PaymentStatus)
from tasks.cc_automated_refund_task import CCAutomatedRefundTask

from .factory import factory_create_direct_pay_account, factory_invoice, factory_invoice_reference, factory_payment


def test_automated_refund_task(session):
    """Test automated refund task, runs without exceptions."""
    CCAutomatedRefundTask().process_cc_refunds()
    assert True


def test_successful_paid_refund(session):
    """Bambora paid, but not GL complete."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.REFUND_REQUESTED.value)
    invoice.disbursement_status_code = DisbursementStatus.UPLOADED.value
    invoice.save()
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED).save()
    payment = factory_payment('PAYBC', invoice_number=invoice.id)
    payment.save()
    # Mock status call. return PAID
    CCAutomatedRefundTask().process_cc_refunds()
    assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value
    assert payment.payment_status_code == PaymentStatus.REFUNDED.value


def test_successful_completed_refund(session):
    """Test successful refund (GL complete)."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.REFUNDED.value)
    invoice.disbursement_status_code = DisbursementStatus.ACKNOWLEDGED.value
    invoice.save()
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED).save()
    payment = factory_payment('PAYBC', invoice_number=invoice.id)
    payment.save()
    # Mock status call. return CMPLT?
    CCAutomatedRefundTask().process_cc_refunds()
    assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value
    assert payment.payment_status_code == PaymentStatus.REFUNDED.value


def test_bad_cfs_refund(session):
    """Test RJCT refund."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.REFUNDED.value)
    invoice.disbursement_status_code = DisbursementStatus.ACKNOWLEDGED.value
    invoice.save()
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED).save()
    # Mock status call. return RJCT?
    CCAutomatedRefundTask().process_cc_refunds()
    assert invoice.invoice_status_code == InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value
