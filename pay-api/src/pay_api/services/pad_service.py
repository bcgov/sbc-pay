# Copyright © 2019 Province of British Columbia
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
"""Service to manage CFS Pre Authorized Debit Payments."""
from typing import Any, Dict
from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentSystem, PaymentStatus
from pay_api.utils.constants import RECEIPT_METHOD_PAD_DAILY
from .payment_line_item import PaymentLineItem


class PadService(PaymentSystemService, CFSService):
    """Service to manage pre authorized debits."""

    def get_payment_system_url(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        return ''

    def get_payment_method_code(self):
        """Return PAD as the system code."""
        return PaymentMethod.PAD.value

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def get_default_invoice_status(self) -> str:
        """Return CREATED as the default invoice status."""
        return InvoiceStatus.CREATED.value

    def get_default_payment_status(self) -> str:
        """Return the default status for payment when created."""
        return PaymentStatus.CREATED.value

    def create_account(self, name: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any], **kwargs):
        """Create an account for the PAD transactions."""
        return self.create_cfs_account(name, contact_info, payment_info=payment_info,
                                       receipt_method=RECEIPT_METHOD_PAD_DAILY)

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number for direct pay."""
        current_app.logger.debug('<create_invoice_pad_service')
        # Do nothing here as the invoice references are created later.

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0,
                       **kwargs):
        """Update invoice on completion."""
        # TODO implement the logic

    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        # TODO not sure if direct pay can be cancelled
        """Adjust the invoice to zero."""

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Get the receipt details by calling PayBC web service."""

    def complete_post_invoice(self, invoice_id: int, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
