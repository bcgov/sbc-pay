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

from pay_api.exceptions import ServiceUnavailableException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.constants import RECEIPT_METHOD_PAD_DAILY
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentSystem, PaymentStatus, CfsAccountStatus
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

    def create_account(self, name: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any],
                       **kwargs) -> CfsAccountModel:
        """Create an account for the PAD transactions."""
        # Create CFS Account model instance and store the bank details
        cfs_account = CfsAccountModel()
        cfs_account.bank_number = payment_info.get('bankInstitutionNumber')
        cfs_account.bank_branch_number = payment_info.get('bankTransitNumber')
        cfs_account.bank_account_number = payment_info.get('bankAccountNumber')

        try:
            # Create CFS account
            cfs_account_details = self.create_cfs_account(name, contact_info, payment_info=payment_info,
                                                          receipt_method=RECEIPT_METHOD_PAD_DAILY)
            # Update model with response values
            cfs_account.payment_instrument_number = cfs_account_details.get('payment_instrument_number', None)
            cfs_account.cfs_account = cfs_account_details.get('account_number')
            cfs_account.cfs_site = cfs_account_details.get('site_number')
            cfs_account.cfs_party = cfs_account_details.get('party_number')
            cfs_account.status = CfsAccountStatus.ACTIVE.value

        except ServiceUnavailableException as e:
            print('Inside catch')
            cfs_account.status = CfsAccountStatus.PENDING.value
            current_app.logger.warning(f'CFS Error {e}')

        return cfs_account

    def update_account(self, name: str, cfs_account: CfsAccountModel, payment_info: Dict[str, Any]) -> CfsAccountModel:
        """Update account in CFS."""
        if str(payment_info.get('bankInstitutionNumber')) != cfs_account.bank_number or \
                str(payment_info.get('bankTransitNumber')) != cfs_account.bank_branch_number or \
                str(payment_info.get('bankAccountNumber')) != cfs_account.bank_account_number:
            # Make the current CFS Account as INACTIVE in DB
            cfs_account.status = CfsAccountStatus.INACTIVE.value
            cfs_account.flush()

            # Create new CFS Account
            updated_cfs_account = CfsAccountModel()
            updated_cfs_account.bank_account_number = payment_info.get('bankAccountNumber')
            updated_cfs_account.bank_number = payment_info.get('bankInstitutionNumber')
            updated_cfs_account.bank_branch_number = payment_info.get('bankTransitNumber')
            updated_cfs_account.cfs_site = cfs_account.cfs_site
            updated_cfs_account.cfs_party = cfs_account.cfs_party
            updated_cfs_account.cfs_account = cfs_account.cfs_account
            updated_cfs_account.payment_account = cfs_account.payment_account

            try:
                # Update bank information in CFS
                bank_details = CFSService.update_bank_details(name=name,
                                                              party_number=cfs_account.cfs_party,
                                                              account_number=cfs_account.cfs_account,
                                                              site_number=cfs_account.cfs_site,
                                                              payment_info=payment_info)
                updated_cfs_account.payment_instrument_number = bank_details.get('payment_instrument_number', None)
                updated_cfs_account.status = CfsAccountStatus.ACTIVE.value
            except ServiceUnavailableException as e:
                updated_cfs_account.status = CfsAccountStatus.PENDING.value
                current_app.logger.warning(f'CFS Error {e}')

            updated_cfs_account.flush()
            return updated_cfs_account
        return cfs_account

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
