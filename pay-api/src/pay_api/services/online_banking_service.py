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
"""Service to manage CFS Online Banking Payments."""
from typing import Any, Dict
from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.utils.enums import PaymentSystem, PaymentMethod, InvoiceStatus, PaymentStatus, CfsAccountStatus
from pay_api.exceptions import ServiceUnavailableException
from .payment_line_item import PaymentLineItem


class OnlineBankingService(PaymentSystemService, CFSService):
    """Service to manage online banking."""

    def get_payment_system_url(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        return ''

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def get_default_invoice_status(self) -> str:
        """Return CREATED as the default invoice status."""
        return InvoiceStatus.CREATED.value

    def get_default_payment_status(self) -> str:
        """Return the default status for payment when created."""
        return PaymentStatus.CREATED.value

    def get_payment_method_code(self):
        """Return ONLINE_BANKING as the system code."""
        return PaymentMethod.ONLINE_BANKING.value

    def create_account(self, name: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any],
                       **kwargs) -> CfsAccountModel:
        """Create an account for the online banking."""
        try:
            # Create CFS Account model instance and store the bank details
            cfs_account = CfsAccountModel()
            # Create CFS account
            cfs_account_details = self.create_cfs_account(name, contact_info, receipt_method=None)
            # Update model with response values
            cfs_account.cfs_site = cfs_account_details.get('site_number')
            cfs_account.cfs_party = cfs_account_details.get('party_number')
            cfs_account.cfs_account = cfs_account_details.get('account_number')
            cfs_account.status = CfsAccountStatus.ACTIVE.value

        except ServiceUnavailableException as e:
            cfs_account.status = CfsAccountStatus.PENDING.value
            current_app.logger.warning(f'CFS Error {e}')

        return cfs_account

    def update_account(self, cfs_account: CfsAccountModel, payment_info: Dict[str, Any]) -> CfsAccountModel:
        """No CFS update needed for online banking account update yet."""

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number for direct pay."""
        current_app.logger.debug('<create_invoice_online_banking')
        # Do nothing here as the roll up happens later after creation of invoice.

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

    # TODO implement this method

    def complete_post_invoice(self, invoice_id: int, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
