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
"""Service to manage Internal Payments.

There are conditions where the payment will be handled internally. For e.g, zero $ or staff payments.
"""

from datetime import datetime
from typing import Any, Dict

from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentSystem, PaymentMethod, InvoiceStatus, PaymentStatus
from pay_api.utils.util import generate_transaction_number
from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class InternalPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_code(self):
        """Return INTERNAL as the system code."""
        return PaymentSystem.INTERNAL.value

    def create_account(self, name: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any],
                       **kwargs) -> any:
        """No Account needed for internal pay."""

    def update_account(self, name: str, cfs_account: any, payment_info: Dict[str, Any]) -> any:
        """No Account needed for direct pay."""

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number."""
        current_app.logger.debug('<create_invoice')

        invoice_reference: InvoiceReference = InvoiceReference.create(invoice.id,
                                                                      generate_transaction_number(invoice.id), None)

        current_app.logger.debug('>create_invoice')
        return invoice_reference

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0,
                       **kwargs):
        """Do nothing as internal payments cannot be updated as it will be completed on creation."""

    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        """Adjust the invoice to zero."""

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Create a static receipt."""
        # Find the invoice using the invoice_number
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'{invoice_reference.invoice_number}', datetime.now(), invoice.total

    def get_payment_method_code(self):
        """Return CC as the method code."""
        return PaymentMethod.INTERNAL.value

    def get_default_invoice_status(self) -> str:
        """Return CREATED as the default invoice status."""
        return InvoiceStatus.CREATED.value

    def get_default_payment_status(self) -> str:
        """Return the default status for payment when created."""
        return PaymentStatus.CREATED.value

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .payment_transaction import PaymentTransaction
        from .payment import Payment
        # Create a payment record
        Payment.create(payment_method=self.get_payment_method_code(),
                       payment_system=self.get_payment_system_code(),
                       payment_status=self.get_default_payment_status(),
                       invoice_number=invoice_reference.invoice_number,
                       invoice_amount=invoice.total,
                       payment_account_id=invoice.payment_account_id)

        transaction: PaymentTransaction = PaymentTransaction.create(invoice.id,
                                                                    {
                                                                        'clientSystemUrl': '',
                                                                        'payReturnUrl': ''
                                                                    })
        transaction.update_transaction(transaction.id, pay_response_url=None)
