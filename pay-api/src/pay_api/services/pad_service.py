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
"""Service to manage CFS Pre Authorized Debit Payments."""

from typing import Any

from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models.refunds_partial import RefundPartialLine
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, PaymentSystem
from pay_api.utils.user_context import user_context

from .base_payment_system import skip_complete_post_invoice_for_sandbox, skip_invoice_for_sandbox
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

    def create_account(
        self,
        identifier: str,  # noqa: ARG002
        contact_info: dict[str, Any],  # noqa: ARG002
        payment_info: dict[str, Any],
        **kwargs,  # noqa: ARG002
    ) -> CfsAccountModel:
        """Create an account for the PAD transactions."""
        # Create CFS Account model instance and store the bank details, set the status as PENDING
        current_app.logger.info(f"Creating PAD account details in PENDING status for {identifier}")
        cfs_account = CfsAccountModel()
        cfs_account.bank_number = payment_info.get("bankInstitutionNumber")
        cfs_account.bank_branch_number = payment_info.get("bankTransitNumber")
        cfs_account.bank_account_number = payment_info.get("bankAccountNumber")
        cfs_account.status = CfsAccountStatus.PENDING.value
        cfs_account.payment_method = PaymentMethod.PAD.value
        return cfs_account

    def update_account(self, name: str, cfs_account: CfsAccountModel, payment_info: dict[str, Any]) -> CfsAccountModel:  # noqa: ARG002
        """Update account in CFS."""
        if (
            str(payment_info.get("bankInstitutionNumber")) != cfs_account.bank_number
            or str(payment_info.get("bankTransitNumber")) != cfs_account.bank_branch_number
            or str(payment_info.get("bankAccountNumber")) != cfs_account.bank_account_number
        ):
            # This means, PAD account details have changed. So update banking details for this CFS account
            # Call cfs service to add new bank info.
            current_app.logger.info(f"Updating PAD account details for {cfs_account}")

            if current_app.config.get("ENVIRONMENT_NAME") == "sandbox":
                current_app.logger.info("Sandbox environment, skipping CFS update.")
                instrument_number = "1"
            else:
                bank_details = CFSService.update_bank_details(
                    name=cfs_account.payment_account.name,
                    party_number=cfs_account.cfs_party,
                    account_number=cfs_account.cfs_account,
                    site_number=cfs_account.cfs_site,
                    payment_info=payment_info,
                )
                instrument_number = bank_details.get("payment_instrument_number", None)

            # Make the current CFS Account as INACTIVE in DB
            current_account_status: str = cfs_account.status
            cfs_account.status = CfsAccountStatus.INACTIVE.value
            cfs_account.flush()

            # Create new CFS Account
            updated_cfs_account = CfsAccountModel()
            updated_cfs_account.bank_account_number = payment_info.get("bankAccountNumber")
            updated_cfs_account.bank_number = payment_info.get("bankInstitutionNumber")
            updated_cfs_account.bank_branch_number = payment_info.get("bankTransitNumber")
            updated_cfs_account.cfs_site = cfs_account.cfs_site
            updated_cfs_account.cfs_party = cfs_account.cfs_party
            updated_cfs_account.cfs_account = cfs_account.cfs_account
            updated_cfs_account.payment_account = cfs_account.payment_account
            updated_cfs_account.payment_method = PaymentMethod.PAD.value
            if current_account_status == CfsAccountStatus.FREEZE.value:
                updated_cfs_account.status = CfsAccountStatus.FREEZE.value
            else:
                updated_cfs_account.status = CfsAccountStatus.ACTIVE.value
            updated_cfs_account.payment_instrument_number = instrument_number
            updated_cfs_account.flush()
        return cfs_account

    @user_context
    @skip_invoice_for_sandbox
    def create_invoice(
        self,
        payment_account: PaymentAccount,  # noqa: ARG002
        line_items: list[PaymentLineItem],  # noqa: ARG002
        invoice: InvoiceModel,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> InvoiceReference:  # pylint: disable=unused-argument
        """Return a static invoice number for direct pay."""
        self.ensure_no_payment_blockers(payment_account)

        # Do nothing here as the invoice references are created later.
        # If the account have credit, deduct the credit amount which will be synced when reconciliation runs.
        pad_account_credit = payment_account.pad_credit or 0
        if pad_account_credit > 0:
            current_app.logger.info(
                f"Account PAD credit {pad_account_credit}, found for {payment_account.auth_account_id}"
            )
        payment_account.pad_credit = 0 if pad_account_credit < invoice.total else pad_account_credit - invoice.total
        payment_account.flush()

    @user_context
    @skip_complete_post_invoice_for_sandbox
    def complete_post_invoice(
        self,
        invoice: InvoiceModel,  # pylint: disable=unused-argument  # noqa: ARG002
        invoice_reference: InvoiceReference,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> None:
        """Complete any post invoice activities if needed."""
        # Publish message to the queue with payment token, so that they can release records on their side.
        self.release_payment_or_reversal(invoice=invoice)

    def process_cfs_refund(
        self,
        invoice: InvoiceModel,  # noqa: ARG002
        payment_account: PaymentAccount,  # noqa: ARG002
        refund_partial: list[RefundPartialLine],  # noqa: ARG002
    ):  # pylint:disable=unused-argument
        """Process refund in CFS."""
        # Move invoice to CREDITED or CANCELLED. There are no refunds for PAD, just cancellation or credit.
        # Credit memos don't return to the bank account.
        return self._refund_and_create_credit_memo(invoice, refund_partial)
