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
"""Service to manage PAYBC services."""

from datetime import UTC, datetime

from flask import current_app

from pay_api.models.distribution_code import DistributionCode as DistributionCodeModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.payment import Payment as PaymentModel
from pay_api.models.payment_line_item import PaymentLineItem as PaymentLineItemModel
from pay_api.models.refund import Refund as RefundModel
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod

STATUS_PAID = "PAID"
STATUS_NOT_PROCESSED = ("PAID", "RJCT")
DECIMAL_PRECISION = ".2f"


class DistributionTask:
    """Task to update distribution details on paybc transactions."""

    @classmethod
    def update_failed_distributions(cls):  # pylint:disable=too-many-locals
        """Update failed distributions.

        Steps:
        1. Get all invoices with status UPDATE_REVENUE_ACCOUNT or UPDATE_REVENUE_ACCOUNT_REFUND.
        2. Find the completed invoice reference for the invoice.
        3. Call the paybc GET service and check if there is any revenue not processed.
        4. If yes, update the revenue details.
        5. Update the invoice status as PAID or REFUNDED and save.
        """
        invoice_statuses = [
            InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value,
            InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value,
        ]
        gl_update_invoices = InvoiceModel.query.filter(InvoiceModel.invoice_status_code.in_(invoice_statuses)).all()
        current_app.logger.debug(f"Found {len(gl_update_invoices)} invoices to update revenue details.")

        if len(gl_update_invoices) == 0:
            return

        access_token: str = DirectPayService().get_token().json().get("access_token")
        paybc_ref_number: str = current_app.config.get("PAYBC_DIRECT_PAY_REF_NUMBER")
        paybc_svc_base_url = current_app.config.get("PAYBC_DIRECT_PAY_BASE_URL")
        for gl_update_invoice in gl_update_invoices:
            payment: PaymentModel = PaymentModel.find_payment_for_invoice(gl_update_invoice.id)
            # For now handle only GL updates for Direct Pay, more to come in future
            if payment.payment_method_code != PaymentMethod.DIRECT_PAY.value:
                cls.update_invoice_to_refunded_or_paid(gl_update_invoice)
                continue

            active_reference = list(
                filter(
                    lambda reference: (reference.status_code == InvoiceReferenceStatus.COMPLETED.value),
                    gl_update_invoice.references,
                )
            )[0]
            payment_url: str = (
                f"{paybc_svc_base_url}/paybc/payment/{paybc_ref_number}/{active_reference.invoice_number}"
            )

            payment_details: dict = cls.get_payment_details(payment_url, access_token)
            if not payment_details:
                current_app.logger.error("No payment details found for invoice.")
                continue

            target_status, target_gl_status = cls.get_status_fields(gl_update_invoice.invoice_status_code)
            if target_status is None or payment_details.get(target_status) == STATUS_PAID:
                has_gl_completed: bool = True
                for revenue in payment_details.get("revenue"):
                    if revenue.get(target_gl_status) in STATUS_NOT_PROCESSED:
                        has_gl_completed = False
                if not has_gl_completed:
                    cls.update_revenue_lines(gl_update_invoice, payment_url, access_token)
                cls.update_invoice_to_refunded_or_paid(gl_update_invoice)

    @classmethod
    def get_status_fields(cls, invoice_status_code: str) -> tuple:
        """Get status fields for invoice status code."""
        if invoice_status_code == InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value:
            # Refund doesn't use a top level status, as partial refunds may occur.
            return None, "refundglstatus"
        return "paymentstatus", "glstatus"

    @classmethod
    def update_revenue_lines(cls, invoice: InvoiceModel, payment_url: str, access_token: str):
        """Update revenue lines for the invoice."""
        post_revenue_payload = cls.generate_post_revenue_payload(invoice)
        OAuthService.post(
            payment_url,
            access_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            post_revenue_payload,
            additional_headers={"Pay-Connector": current_app.config.get("PAY_CONNECTOR_AUTH")},
        )

    @classmethod
    def generate_post_revenue_payload(cls, invoice: InvoiceModel):
        """Generate the payload for POSTing revenue to paybc."""
        post_revenue_payload = {"revenue": []}

        payment_line_items = PaymentLineItemModel.find_by_invoice_ids([invoice.id])
        index: int = 0

        for payment_line_item in payment_line_items:
            fee_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                payment_line_item.fee_distribution_id
            )

            if payment_line_item.total is not None and payment_line_item.total > 0:
                index = index + 1
                post_revenue_payload["revenue"].append(
                    cls.get_revenue_details(index, fee_distribution_code, payment_line_item.total)
                )

            if payment_line_item.service_fees is not None and payment_line_item.service_fees > 0:
                service_fee_distribution_code = DistributionCodeModel.find_by_id(
                    fee_distribution_code.distribution_code_id
                )
                index = index + 1
                post_revenue_payload["revenue"].append(
                    cls.get_revenue_details(
                        index,
                        service_fee_distribution_code,
                        payment_line_item.service_fees,
                    )
                )
        return post_revenue_payload

    @classmethod
    def get_payment_details(cls, payment_url: str, access_token: str):
        """Get the receipt details by calling PayBC web service."""
        payment_response = OAuthService.get(
            payment_url,
            access_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            additional_headers={"Pay-Connector": current_app.config.get("PAY_CONNECTOR_AUTH")},
        ).json()
        return payment_response

    @classmethod
    def get_revenue_details(cls, index: int, dist_code: DistributionCodeModel, amount: float):
        """Get the receipt details by calling PayBC web service."""
        revenue_account = (
            f"{dist_code.client}.{dist_code.responsibility_centre}."
            f"{dist_code.service_line}.{dist_code.stob}.{dist_code.project_code}"
            f".000000.0000"
        )

        return {
            "lineNumber": str(index),
            "revenueAccount": revenue_account,
            "revenueAmount": format(amount, DECIMAL_PRECISION),
        }

    @classmethod
    def update_invoice_to_refunded_or_paid(cls, invoice: InvoiceModel):
        """Update the invoice status."""
        if invoice.invoice_status_code == InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value:
            # No more work is needed to ensure it was posted to gl.
            refund = RefundModel.find_latest_by_invoice_id(invoice.id)
            refund.gl_posted = datetime.now(tz=UTC)
            refund.save()
            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
        else:
            invoice.invoice_status_code = InvoiceStatus.PAID.value
        invoice.save()
        current_app.logger.info(f"Updated invoice : {invoice.id}")
