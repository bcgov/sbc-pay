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
"""Service to manage CFS Online Banking Payments."""

from typing import Any, Dict, List

from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models.refunds_partial import RefundPartialLine
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod, PaymentSystem

from .payment_line_item import PaymentLineItem


class OnlineBankingService(PaymentSystemService, CFSService):
    """Service to manage online banking."""

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def get_payment_method_code(self):
        """Return ONLINE_BANKING as the system code."""
        return PaymentMethod.ONLINE_BANKING.value

    def create_account(
        self, identifier: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any], **kwargs
    ) -> CfsAccountModel:
        """Create an account for the online banking."""
        # Create CFS Account model instance and set the status as PENDING
        cfs_account = CfsAccountModel()
        cfs_account.status = CfsAccountStatus.PENDING.value
        cfs_account.payment_method = PaymentMethod.ONLINE_BANKING.value
        return cfs_account

    def create_invoice(
        self, payment_account: PaymentAccount, line_items: List[PaymentLineItem], invoice: Invoice, **kwargs
    ) -> InvoiceReference:
        """Return a static invoice number for online banking."""
        self.ensure_no_payment_blockers(payment_account)
        # Do nothing here as the roll up happens later after creation of invoice.
        # We don't update the credits here like PAD, because we need the dialog to show the user we're using
        # a credit to pay for this invoice. So they don't send extra unnecessary money.

    def get_receipt(
        self,
        payment_account: PaymentAccount,
        pay_response_url: str,
        invoice_reference: InvoiceReference,
    ):
        """Get the receipt details by calling PayBC web service."""

    def apply_credit(self, invoice: Invoice) -> None:
        """Apply credit to the invoice."""
        self.release_payment_or_reversal(invoice=invoice)

    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug("<cancel_invoice %s, %s", payment_account, inv_number)
        self.reverse_invoice(inv_number)

    def process_cfs_refund(
        self,
        invoice: InvoiceModel,
        payment_account: PaymentAccount,
        refund_partial: List[RefundPartialLine],
    ):  # pylint:disable=unused-argument
        """Process refund in CFS."""
        return super()._refund_and_create_credit_memo(invoice, refund_partial)
