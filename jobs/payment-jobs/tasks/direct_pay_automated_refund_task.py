# Copyright © 2022 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Task to create CFS invoices offline."""
from datetime import datetime
from typing import List

from flask import current_app
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import Refund as RefundModel
from pay_api.models.invoice import Invoice
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import (
    AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus)
from sentry_sdk import capture_message

from tasks.common.dataclasses import OrderStatus
from tasks.common.enums import PaymentDetailsGlStatus, PaymentDetailsStatus


class DirectPayAutomatedRefundTask:  # pylint:disable=too-few-public-methods
    """
    Task to query CAS for order statuses of invoices.

    Ensures invoices have been processed correctly by the GL.
    This handles payment reconciliation for automated credit card refunds via REST
    instead of a feedback file (no provided CSV or EJV feedback file).
    Utilizes invoice.disbursement_status_code.
    """

    @classmethod
    def process_cc_refunds(cls):
        """Check Credit Card refunds through CAS service."""
        cls.handle_non_complete_credit_card_refunds()

    @classmethod
    def handle_non_complete_credit_card_refunds(cls):
        """
        Process non complete credit card refunds.

        1. Find all invoices that use Direct Pay (Credit Card) in REFUND_REQUESTED or REFUNDED
           excluding invoices with refunds that have gl_posted.
           Initial state for refunds is REFUND INPRG.
        2. Get order status for CFS (refundstatus, revenue.refundglstatus)
            2.1. Check for refundStatus = PAID and invoice = REFUND_REQUESTED:
                Set invoice and payment = REFUNDED
            2.2. Check for refundStatus = CMPLT or None (None is for refunds done manually)
                Set invoice and payment = REFUNDED (incase we skipped the condition above).
                Set refund.gl_posted = now()
            2.3. Check for refundGLstatus = RJCT
                Set invoice = UPDATE_REVENUE_ACCOUNT_REFUND (should be picked up by distribution_task to update GL).
        """
        include_invoice_statuses = [InvoiceStatus.REFUND_REQUESTED.value, InvoiceStatus.REFUNDED.value]
        invoices: List[InvoiceModel] = InvoiceModel.query \
            .outerjoin(RefundModel, RefundModel.invoice_id == Invoice.id)\
            .filter(InvoiceModel.payment_method_code == PaymentMethod.DIRECT_PAY.value) \
            .filter(InvoiceModel.invoice_status_code.in_(include_invoice_statuses)) \
            .filter(RefundModel.gl_posted.is_(None)) \
            .order_by(InvoiceModel.created_on.asc()).all()

        current_app.logger.info(f'Found {len(invoices)} invoices to process for refunds.')
        for invoice in invoices:
            current_app.logger.debug(f'Processing invoice {invoice.id} - created on: {invoice.created_on}')
            try:
                status = OrderStatus.from_dict(cls._query_order_status(invoice))
                if cls._is_glstatus_rejected(status):
                    cls._refund_update_revenue(invoice)
                elif cls._is_status_paid_and_invoice_refund_requested(status, invoice):
                    cls._refund_paid(invoice)
                elif cls._is_status_complete(status):
                    if status.refundstatus is None:
                        current_app.logger.info(
                            'Refund status was blank, setting to complete - this was an existing manual refund.')
                    cls._refund_complete(invoice)
                else:
                    current_app.logger.info(f'No action taken for invoice {invoice.id}.')
            except Exception as e:  # NOQA # pylint: disable=broad-except disable=invalid-name
                capture_message(f'Error on processing credit card refund - invoice id={invoice.id}'
                                f'status={invoice.invoice_status_code} ERROR : {str(e)}', level='error')
                current_app.logger.error(e)

    @classmethod
    def _query_order_status(cls, invoice: Invoice):
        """Request order status for CFS."""
        access_token: str = DirectPayService().get_token().json().get('access_token')
        paybc_ref_number: str = current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')
        paybc_svc_base_url = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL')
        completed_reference = list(
            filter(lambda reference: (reference.status_code == InvoiceReferenceStatus.COMPLETED.value),
                   invoice.references))[0]
        payment_url: str = \
            f'{paybc_svc_base_url}/paybc/payment/{paybc_ref_number}/{completed_reference.invoice_number}'
        payment_response = OAuthService.get(payment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON).json()
        return payment_response

    @classmethod
    def _refund_update_revenue(cls, invoice: Invoice):
        current_app.logger.info(f'Setting invoice id {invoice.id} to UPDATE_REVENUE_ACCOUNT_REFUND.')
        invoice.invoice_status_code = InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value
        invoice.save()

    @classmethod
    def _refund_paid(cls, invoice: Invoice):
        """Refund was paid by Bambora. Set disbursement to acknowledged."""
        if invoice.invoice_status_code != InvoiceStatus.REFUND_REQUESTED.value:
            return
        cls._set_invoice_and_payment_to_refunded(invoice)

    @classmethod
    def _refund_complete(cls, invoice: Invoice):
        """Refund was successfully posted to a GL. Set disbursement to reversed (filtered out)."""
        # Set these to refunded, incase we skipped the PAID state and went to CMPLT
        cls._set_invoice_and_payment_to_refunded(invoice)
        current_app.logger.info(
            'Refund complete - GL was posted - setting refund gl_posted to now.')
        refund = RefundModel.find_by_invoice_id(invoice.id)
        refund.gl_posted = datetime.now()
        refund.save()

    @staticmethod
    def _is_glstatus_rejected(status: OrderStatus) -> bool:
        """Check for bad refundglstatus."""
        return any(line.refundglstatus == PaymentDetailsGlStatus.RJCT
                   for line in status.revenue)

    @staticmethod
    def _is_status_paid_and_invoice_refund_requested(status: OrderStatus, invoice: Invoice) -> bool:
        """Check for successful refund and invoice status = REFUND_REQUESTED."""
        return status.refundstatus == PaymentDetailsStatus.PAID \
            and invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

    @staticmethod
    def _is_status_complete(status: OrderStatus) -> bool:
        """Check for successful refund, or if the refund was done manually."""
        return status.refundstatus == PaymentDetailsStatus.CMPLT or status.refundstatus is None

    @staticmethod
    def _set_invoice_and_payment_to_refunded(invoice: Invoice):
        """Set invoice and payment to REFUNDED."""
        current_app.logger.info(f'Setting invoice id {invoice.id} and payment to REFUNDED.')
        invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
        invoice.save()
        payment = PaymentModel.find_payment_for_invoice(invoice.id)
        payment.payment_status_code = PaymentStatus.REFUNDED.value
        payment.save()
