# Copyright © 2024 Province of British Columbia
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
"""Service to manage Receipt."""

from typing import Any, Dict, Self

from flask import current_app
from sbc_common_components.utils.camel_case_response import camelcase_dict

from pay_api.exceptions import BusinessException
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentMethod as PaymentMethodModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import (
    AuthHeaderType,
    ContentType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentSystem,
)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context
from pay_api.utils.util import get_local_formatted_date

from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .oauth_service import OAuthService


class Receipt:  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment Line Item operations."""

    @staticmethod
    def find_by_id(receipt_id: int) -> Self:
        """Find by receipt id."""
        receipt = ReceiptModel.find_by_id(receipt_id)
        current_app.logger.debug(">find_by_id")
        return receipt

    @staticmethod
    def find_by_invoice_id_and_receipt_number(invoice_id: int, receipt_number: str = None) -> Self:
        """Find by the combination of invoce id and receipt number."""
        receipt = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id, receipt_number)
        current_app.logger.debug(">find_by_invoice_id_and_receipt_number")
        return receipt

    @staticmethod
    @user_context
    def create_receipt(
        invoice_identifier: str,
        filing_data: Dict[str, Any],
        skip_auth_check: bool = False,
        **kwargs,
    ):
        """Create receipt."""
        current_app.logger.debug("<create receipt initiated")
        receipt_dict = {
            "templateName": "payment_receipt",
            "reportName": filing_data.pop("fileName", "payment_receipt"),
        }

        template_vars = Receipt.get_receipt_details(filing_data, invoice_identifier, skip_auth_check)
        template_vars.update(filing_data)

        receipt_dict["templateVars"] = template_vars

        current_app.logger.debug(
            f"<OAuthService invoked from receipt.py {current_app.config.get('REPORT_API_BASE_URL')}"
        )

        pdf_response = OAuthService.post(
            current_app.config.get("REPORT_API_BASE_URL"),
            kwargs["user"].bearer_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            receipt_dict,
        )
        current_app.logger.debug("<OAuthService responded to receipt.py")

        return pdf_response

    @staticmethod
    def get_receipt_details(filing_data, invoice_identifier, skip_auth_check):
        """Return receipt details."""
        receipt_details: dict = {}
        # invoice number mandatory
        invoice_data = Invoice.find_by_id(invoice_identifier, skip_auth_check=skip_auth_check)

        is_pending_invoice = (
            invoice_data.payment_method_code
            in (PaymentMethod.PAD.value, PaymentMethod.EJV.value, PaymentMethod.EFT.value, PaymentMethod.INTERNAL.value)
            and invoice_data.invoice_status_code != InvoiceStatus.PAID.value
        )
        if not is_pending_invoice and not invoice_data.receipts:
            raise BusinessException(Error.INVALID_REQUEST)

        invoice_reference = InvoiceReference.find_completed_reference_by_invoice_id(invoice_data.id)

        receipt_details["invoiceNumber"] = invoice_reference.invoice_number
        if invoice_data.payment_method_code == PaymentSystem.INTERNAL.value and invoice_data.routing_slip:
            receipt_details["routingSlipNumber"] = invoice_data.routing_slip
        receipt_details["receiptNumber"] = None if is_pending_invoice else invoice_data.receipts[0].receipt_number
        receipt_details["filingIdentifier"] = filing_data.get("filingIdentifier", invoice_data.filing_id)
        receipt_details["bcOnlineAccountNumber"] = invoice_data.bcol_account

        payment_method = PaymentMethodModel.find_by_code(invoice_data.payment_method_code)

        receipt_details["paymentMethod"] = payment_method.code
        if invoice_data.payment_method_code != PaymentSystem.INTERNAL.value:
            receipt_details["paymentMethodDescription"] = payment_method.description
        receipt_details["invoice"] = camelcase_dict(invoice_data.asdict(), {})
        # Format date to display in report.
        receipt_details["invoice"]["createdOn"] = get_local_formatted_date(invoice_data.created_on)
        return receipt_details

    @staticmethod
    def get_nsf_receipt_details(payment_id):
        """Return NSF receipt details, which can contain multiple invoices, combine these in PLI."""
        receipt_details = {}
        invoices = Invoice.find_invoices_for_payment(payment_id, InvoiceReferenceStatus.COMPLETED.value)
        nsf_invoice = next(
            (invoice for invoice in invoices if invoice.payment_method_code == PaymentMethod.CC.value),
            None,
        )
        payment = PaymentModel.find_by_id(payment_id)
        receipt_details["invoiceNumber"] = payment.invoice_number
        receipt_details["receiptNumber"] = payment.receipt_number
        receipt_details["paymentMethodDescription"] = "Credit Card"
        non_nsf_invoices = [inv for inv in invoices if nsf_invoice is None or inv.id != nsf_invoice.id]
        # We don't generate a CC invoice for EFT overdue payments.
        if not nsf_invoice:
            nsf_invoice = Invoice()
            nsf_invoice.created_on = payment.payment_date
            nsf_invoice.paid = 0
            nsf_invoice.payment_line_items = []
            nsf_invoice.service_fees = 0
            nsf_invoice.total = 0
        nsf_invoice.details = []
        for invoice in non_nsf_invoices:
            nsf_invoice.payment_line_items.extend(invoice.payment_line_items)
            nsf_invoice.total += invoice.total
            nsf_invoice.service_fees += invoice.service_fees
            nsf_invoice.paid += invoice.paid
            nsf_invoice.details.extend(invoice.details or [])
        receipt_details["invoice"] = camelcase_dict(nsf_invoice.asdict(), {})
        receipt_details["invoice"]["createdOn"] = get_local_formatted_date(nsf_invoice.created_on)
        return receipt_details
