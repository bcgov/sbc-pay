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
"""Task to handle Direct Pay automated refunds."""
from datetime import datetime, timezone
from typing import List

from flask import current_app
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.models.invoice import Invoice
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import (
    AuthHeaderType,
    ContentType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    TransactionStatus, RefundStatus,
)

from tasks.common.dataclasses import OrderStatus
from tasks.common.enums import PaymentDetailsGlStatus


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
        cls.handle_credit_card_refund_partials()

    @classmethod
    def handle_credit_card_refund_partials(cls):
        """Process credit card partial refunds."""
        invoices: List[InvoiceModel] = (
            InvoiceModel.query
            .join(RefundsPartialModel, RefundsPartialModel.invoice_id == Invoice.id)
            .join(RefundModel, RefundModel.id == RefundsPartialModel.refund_id)
            .filter(InvoiceModel.payment_method_code == PaymentMethod.DIRECT_PAY.value)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            .filter(RefundModel.status.in_([RefundStatus.APPROVAL_NOT_REQUIRED.value, RefundStatus.APPROVED.value]))
            .filter(RefundsPartialModel.gl_posted.is_(None))
            .order_by(InvoiceModel.id, RefundsPartialModel.id)
            .distinct(InvoiceModel.id)
            .all()
        )

        current_app.logger.info(f"Found {len(invoices)} invoices to process for partial refunds.")
        for invoice in invoices:
            try:
                current_app.logger.debug(f"Processing invoice: {invoice.id} - refund_date: {invoice.refund_date}")
                status = OrderStatus.from_dict(cls._query_order_status(invoice))
                if cls._is_glstatus_rejected_or_declined(status):
                    cls._refund_error(status=status, invoice=invoice)
                elif cls._is_status_complete(status):
                    cls._refund_complete(invoice=invoice, is_partial_refund=True)
                else:
                    current_app.logger.info("No action taken for invoice partial refund.")
            except Exception as e:  # NOQA # pylint: disable=broad-except disable=invalid-name
                current_app.logger.error(
                    f"Error on processing credit card partial refund - invoice: {invoice.id}"
                    f"status={invoice.invoice_status_code} ERROR : {str(e)}",
                    exc_info=True,
                )

    @classmethod
    def handle_non_complete_credit_card_refunds(cls):
        """
        Process non complete credit card refunds.

        1. Find all invoices that use Direct Pay (Credit Card) in REFUND_REQUESTED or REFUNDED
           excluding invoices with refunds that have gl_posted or gl_error.
           Initial state for refunds is REFUND INPRG.
        2. Get order status for CFS (refundstatus, revenue.refundglstatus)
            2.1. Check for all revenue.refundGLstatus = PAID and invoice = REFUND_REQUESTED:
                Set invoice and payment = REFUNDED
            2.2. Check for all revenue.refundGLstatus = CMPLT
                Set invoice and payment = REFUNDED (incase we skipped the condition above).
                Set refund.gl_posted = now()
            2.3. Check for any revenue.refundGLstatus = RJCT
                Log the error down, contact PAYBC if this happens.
                Set refund.gl_error = <error message>
        """
        include_invoice_statuses = [
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.REFUNDED.value,
        ]
        invoices: List[InvoiceModel] = (
            InvoiceModel.query.outerjoin(RefundModel, RefundModel.invoice_id == Invoice.id)
            .filter(InvoiceModel.payment_method_code == PaymentMethod.DIRECT_PAY.value)
            .filter(InvoiceModel.invoice_status_code.in_(include_invoice_statuses))
            .filter(RefundModel.gl_posted.is_(None) & RefundModel.gl_error.is_(None)
                    & RefundModel.status.in_([RefundStatus.APPROVAL_NOT_REQUIRED.value, RefundStatus.APPROVED.value]))
            .order_by(InvoiceModel.created_on.asc())
            .all()
        )

        current_app.logger.info(f"Found {len(invoices)} invoices to process for refunds.")
        for invoice in invoices:
            try:
                # Cron is setup to run between 6 to 8 UTC. Feedback is updated after 11pm.
                current_app.logger.debug(f"Processing invoice: {invoice.id} - created on: {invoice.created_on}")
                status = OrderStatus.from_dict(cls._query_order_status(invoice))
                if cls._is_glstatus_rejected_or_declined(status):
                    cls._refund_error(status, invoice)
                elif cls._is_status_paid_and_invoice_refund_requested(status, invoice):
                    cls._refund_paid(invoice)
                elif cls._is_status_complete(status):
                    cls._refund_complete(invoice)
                else:
                    current_app.logger.info("No action taken for invoice.")
            except Exception as e:  # NOQA # pylint: disable=broad-except disable=invalid-name
                current_app.logger.error(
                    f"Error on processing credit card refund - invoice: {invoice.id}"
                    f"status={invoice.invoice_status_code} ERROR : {str(e)}",
                    exc_info=True,
                )

    @classmethod
    def _query_order_status(cls, invoice: Invoice):
        """Request order status for CFS."""
        access_token: str = DirectPayService().get_token().json().get("access_token")
        paybc_ref_number: str = current_app.config.get("PAYBC_DIRECT_PAY_REF_NUMBER")
        paybc_svc_base_url = current_app.config.get("PAYBC_DIRECT_PAY_BASE_URL")
        completed_reference = list(
            filter(
                lambda reference: (reference.status_code == InvoiceReferenceStatus.COMPLETED.value),
                invoice.references,
            )
        )[0]
        payment_url: str = f"{paybc_svc_base_url}/paybc/payment/{paybc_ref_number}/{completed_reference.invoice_number}"
        payment_response = OAuthService.get(
            payment_url,
            access_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            additional_headers={"Pay-Connector": current_app.config.get("PAY_CONNECTOR_AUTH")},
        ).json()
        return payment_response

    @classmethod
    def _refund_error(cls, status: OrderStatus, invoice: Invoice):
        """Log error for rejected GL status."""
        current_app.logger.error(
            f"Refund error - Invoice: {invoice.id} - detected RJCT/DECLINED on refund," "contact PAYBC if it's RJCT."
        )
        errors = " ".join(
            [
                refund_data.refundglerrormessage.strip()
                for revenue_line in status.revenue
                for refund_data in revenue_line.refund_data
            ]
        )[:250]
        current_app.logger.error(f"Refund error - Invoice: {invoice.id} - glerrormessage: {errors}")
        refund = RefundModel.find_latest_by_invoice_id(invoice.id)
        refund.gl_error = errors
        refund.save()

    @classmethod
    def _refund_paid(cls, invoice: Invoice):
        """Refund was paid by Bambora. Update invoice and payment."""
        if invoice.invoice_status_code != InvoiceStatus.REFUND_REQUESTED.value:
            return
        cls._set_invoice_and_payment_to_refunded(invoice)

    @classmethod
    def _refund_complete(cls, invoice: Invoice, is_partial_refund: bool = False):
        """Refund was successfully posted to a GL. Set gl_posted to now (filtered out)."""
        # Set these to refunded, incase we skipped the PAID state and went to CMPLT
        if not is_partial_refund:
            cls._set_invoice_and_payment_to_refunded(invoice)
        else:
            cls._set_refund_partials_posted(invoice)
        current_app.logger.info("Refund complete - GL was posted - setting refund.gl_posted to now.")
        refund = RefundModel.find_latest_by_invoice_id(invoice.id)
        refund.gl_posted = datetime.now(tz=timezone.utc)
        refund.save()

    @staticmethod
    def _is_glstatus_rejected_or_declined(status: OrderStatus) -> bool:
        """Check for bad refundglstatus."""
        return any(
            refund_data.refundglstatus in [PaymentDetailsGlStatus.RJCT, PaymentDetailsGlStatus.DECLINED]
            for line in status.revenue
            for refund_data in line.refund_data
        )

    @staticmethod
    def _is_status_paid_and_invoice_refund_requested(status: OrderStatus, invoice: Invoice) -> bool:
        """Check for successful refund and invoice status = REFUND_REQUESTED."""
        for line in status.revenue:
            if len(line.refund_data) == 0:
                return False
            for refund_data in line.refund_data:
                if refund_data.refundglstatus != PaymentDetailsGlStatus.PAID:
                    return False
        return invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

    @staticmethod
    def _is_status_complete(status: OrderStatus) -> bool:
        """Check for successful refund."""
        for line in status.revenue:
            if len(line.refund_data) == 0:
                return False
            for refund_data in line.refund_data:
                if refund_data.refundglstatus != PaymentDetailsGlStatus.CMPLT:
                    return False
        return True

    @staticmethod
    def _set_invoice_and_payment_to_refunded(invoice: Invoice):
        """Set invoice and payment to REFUNDED."""
        current_app.logger.info("Invoice & Payment set to REFUNDED, add refund_date.")
        invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
        invoice.refund_date = datetime.now(tz=timezone.utc)
        invoice.save()
        payment = PaymentModel.find_payment_for_invoice(invoice.id)
        payment.payment_status_code = PaymentStatus.REFUNDED.value
        payment.save()
        DirectPayService().release_payment_or_reversal(invoice, TransactionStatus.REVERSED.value)

    @classmethod
    def _set_refund_partials_posted(cls, invoice: Invoice):
        """Set Refund partials gl_posted."""
        refund_partials = cls._find_refund_partials_by_invoice_id(invoice.id)
        for refund_partial in refund_partials:
            refund_partial.gl_posted = datetime.now(tz=timezone.utc)
            refund_partial.save()

    @staticmethod
    def _find_refund_partials_by_invoice_id(invoice_id: int) -> List[RefundsPartialModel]:
        """Retrieve Refunds partials by invoice id to be processed."""
        return (
            RefundsPartialModel.query.filter(RefundsPartialModel.invoice_id == invoice_id)
            .filter(RefundModel.gl_posted.is_(None) & RefundModel.gl_error.is_(None))
            .all()
        )
