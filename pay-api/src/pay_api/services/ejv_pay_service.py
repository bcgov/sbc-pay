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
"""Service to manage EJV Payments.

There are conditions where the payment will be handled for government accounts.
"""

from datetime import datetime

from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem
from pay_api.utils.util import generate_transaction_number

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class EjvPayService(PaymentSystemService, OAuthService):
    """Service to manage EJV pay accounts."""

    def get_payment_system_code(self):
        """Return CGI as the system code."""
        return PaymentSystem.CGI.value

    def get_payment_method_code(self):
        """Return EJV as the method code."""
        return PaymentMethod.EJV.value

    def get_default_invoice_status(self) -> str:
        """Return CREATED as the default invoice status."""
        return InvoiceStatus.APPROVED.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number."""
        current_app.logger.debug('<create_invoice')
        invoice_reference: InvoiceReference = None
        # If the account is not billable, then create records,
        if not payment_account.billable:
            invoice_reference = InvoiceReference.create(invoice.id, generate_transaction_number(invoice.id), None)
        # else Do nothing here as the invoice references are created later.
        return invoice_reference

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .payment import Payment
        from .receipt import Receipt

        if invoice_reference and invoice_reference.status_code == InvoiceReferenceStatus.ACTIVE.value:
            # Create a payment record
            Payment.create(payment_method=self.get_payment_method_code(),
                           payment_system=self.get_payment_system_code(),
                           payment_status=PaymentStatus.COMPLETED.value,
                           invoice_number=invoice_reference.invoice_number,
                           invoice_amount=invoice.total,
                           payment_account_id=invoice.payment_account_id)
            invoice.invoice_status_code = InvoiceStatus.PAID.value
            invoice.paid = invoice.total
            invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
            # Create receipt.
            receipt = Receipt()
            receipt.receipt_number = invoice_reference.invoice_number
            receipt.receipt_amount = invoice.total
            receipt.invoice_id = invoice.id
            receipt.receipt_date = datetime.now()

            invoice_reference.flush()
            receipt.flush()
            invoice.save()

        # Publish message to the queue with payment token, so that they can release records on their side.
        self._release_payment(invoice=invoice)
