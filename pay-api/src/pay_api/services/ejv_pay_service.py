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
"""Service to manage EJV Payments.

There are conditions where the payment will be handled for government accounts.
"""

from typing import List
from flask import current_app

from pay_api.models import Invoice as InvoiceModel
from pay_api.models.refunds_partial import RefundPartialLine
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentSystem
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

    def create_invoice(self, payment_account: PaymentAccount, line_items: List[PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number."""
        self.ensure_no_payment_blockers(payment_account, invoice)
        invoice_reference: InvoiceReference = None
        # If the account is not billable, then create records,
        if not payment_account.billable:
            current_app.logger.debug(f'Non billable invoice {invoice.id}, '
                                     f'Auth Account : {payment_account.auth_account_id}')
            invoice_reference = InvoiceReference.create(invoice.id, generate_transaction_number(invoice.id), None)
        # else Do nothing here as the invoice references are created later.
        return invoice_reference

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
        if invoice_reference and invoice_reference.status_code == InvoiceReferenceStatus.ACTIVE.value:
            # Create a payment record
            self.complete_payment(invoice, invoice_reference)

        # Publish message to the queue with payment token, so that they can release records on their side.
        self._release_payment(invoice=invoice)

    def process_cfs_refund(self, invoice: InvoiceModel,
                           payment_account: PaymentAccount,
                           refund_partial: List[RefundPartialLine]) -> str:  # pylint:disable=unused-argument
        """Do nothing to process refund; as the refund is handled by CRON job.

        Return the status after checking invoice status.
            1. If invoice status is APPROVED:
            1.1 return REFUND_REQUESTED if there is an ACTIVE invoice_reference
            1.2 else return CANCELLED (as no refund process is needed for this as JV hasn't started yet)
            2. If invoice status is PAID
            2.1 Return REFUND_REQUESTED
        """
        current_app.logger.info(f'Received JV refund for invoice {invoice.id}, {invoice.invoice_status_code}')
        if not payment_account.billable:
            return InvoiceStatus.REFUNDED.value
        if invoice.invoice_status_code == InvoiceStatus.APPROVED.value:
            if InvoiceReference.find_active_reference_by_invoice_id(invoice.id):
                return InvoiceStatus.REFUND_REQUESTED.value
            return InvoiceStatus.CANCELLED.value
        return InvoiceStatus.REFUND_REQUESTED.value
