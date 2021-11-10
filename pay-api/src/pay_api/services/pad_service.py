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

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, PaymentSystem

from .payment_line_item import PaymentLineItem


class PadService(PaymentSystemService, CFSService):
    """Service to manage pre authorized debits."""

    def get_payment_method_code(self):
        """Return PAD as the system code."""
        return PaymentMethod.PAD.value

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def get_default_invoice_status(self) -> str:
        """Return CREATED as the default invoice status."""
        return InvoiceStatus.APPROVED.value

    def create_account(self, identifier: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any],
                       **kwargs) -> CfsAccountModel:
        """Create an account for the PAD transactions."""
        # Create CFS Account model instance and store the bank details, set the status as PENDING
        cfs_account = CfsAccountModel()
        cfs_account.bank_number = payment_info.get('bankInstitutionNumber')
        cfs_account.bank_branch_number = payment_info.get('bankTransitNumber')
        cfs_account.bank_account_number = payment_info.get('bankAccountNumber')
        cfs_account.status = CfsAccountStatus.PENDING.value
        return cfs_account

    def update_account(self, name: str, cfs_account: CfsAccountModel, payment_info: Dict[str, Any]) -> CfsAccountModel:
        """Update account in CFS."""
        if str(payment_info.get('bankInstitutionNumber')) != cfs_account.bank_number or \
                str(payment_info.get('bankTransitNumber')) != cfs_account.bank_branch_number or \
                str(payment_info.get('bankAccountNumber')) != cfs_account.bank_account_number:
            # This means, PAD account details have changed. So update banking details for this CFS account
            # Call cfs service to add new bank info.
            bank_details = CFSService.update_bank_details(name=cfs_account.payment_account.name,
                                                          party_number=cfs_account.cfs_party,
                                                          account_number=cfs_account.cfs_account,
                                                          site_number=cfs_account.cfs_site,
                                                          payment_info=payment_info)

            instrument_number = bank_details.get('payment_instrument_number', None)

            # Make the current CFS Account as INACTIVE in DB
            current_account_status: str = cfs_account.status
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
            if current_account_status == CfsAccountStatus.FREEZE.value:
                updated_cfs_account.status = CfsAccountStatus.FREEZE.value
            else:
                updated_cfs_account.status = CfsAccountStatus.ACTIVE.value
            updated_cfs_account.payment_instrument_number = instrument_number
            updated_cfs_account.flush()
        return cfs_account

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number for direct pay."""
        current_app.logger.debug('<create_invoice_pad_service')
        # Do nothing here as the invoice references are created later.
        # If the account have credit, deduct the credit amount which will be synced when reconciliation runs.
        account_credit = payment_account.credit or 0
        payment_account.credit = 0 if account_credit < invoice.total else account_credit - invoice.total
        payment_account.flush()

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
        # Publish message to the queue with payment token, so that they can release records on their side.
        self._release_payment(invoice=invoice)

    def process_cfs_refund(self, invoice: InvoiceModel):
        """Process refund in CFS."""
        super()._refund_and_create_credit_memo(invoice)
