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
"""Task for linking electronic funds transfers."""

from datetime import datetime
from typing import List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services import EFTShortNamesService
from pay_api.services.receipt import Receipt
from pay_api.utils.enums import CfsAccountStatus, EFTShortnameState, InvoiceReferenceStatus, InvoiceStatus
from pay_api.utils.util import generate_receipt_number
from sentry_sdk import capture_message


class ElectronicFundsTransferTask:  # pylint:disable=too-few-public-methods
    """Task to link electronic funds transfers."""

    @classmethod
    def link_electronic_funds_transfers(cls):
        """Create invoice in CFS.

        Steps:
        1. Find all pending EFT Short Names in a LINKED state.
        2. Receipts created in CAS representing the EFT.
        3. Apply the receipts to the invoices.
        4. Notify mailer
        """
        eft_short_names = cls._get_eft_short_names_by_state(EFTShortnameState.LINKED.value)
        for eft_short_name in eft_short_names:
            try:
                current_app.logger.debug(f'Linking Electronic Funds Transfer: {eft_short_name.id}')
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(
                    eft_short_name.auth_account_id)
                cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)
                eft_credit: EFTCreditModel = EFTCreditModel.find_by_payment_account_id(payment_account.id)

                payment = db.session.query(PaymentModel) \
                    .join(PaymentAccountModel, PaymentAccountModel.id == PaymentModel.payment_account_id) \
                    .join(EFTCreditModel, EFTCreditModel.payment_account_id == PaymentAccountModel.id) \
                    .join(EFTShortnameModel, EFTShortnameModel.id == EFTCreditModel.short_name_id) \
                    .filter(EFTShortnameModel.id == eft_short_name.id).first()

                receipt_number = generate_receipt_number(payment.id)
                CFSService.create_cfs_receipt(
                    cfs_account=cfs_account,
                    rcpt_number=receipt_number,
                    rcpt_date=payment.payment_date.strftime('%Y-%m-%d'),
                    amount=payment.invoice_amount,
                    payment_method=payment_account.payment_method,
                    access_token=CFSService.get_fas_token().json().get('access_token'))

                # apply receipt to cfs_account
                total_invoice_amount = cls._apply_electronic_funds_transfers_to_pending_invoices(
                    eft_short_name, payment)
                current_app.logger.debug(f'Total Invoice Amount : {total_invoice_amount}')

                eft_credit.remaining_amount = eft_credit.amount - total_invoice_amount

                eft_short_name.save()

            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on Electronics Funds Transfer ID:={eft_short_name.id}, '
                    f'electronic funds transfer : {eft_short_name.id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue

    @classmethod
    def _get_eft_short_names_by_state(cls, state: EFTShortnameState) -> List[EFTShortnameModel]:
        """Get electronic funds transfer by state."""
        query = db.session.query(EFTShortnameModel) \
            .join(PaymentAccountModel, PaymentAccountModel.auth_account_id == EFTShortnameModel.auth_account_id) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .filter(CfsAccountModel.status == CfsAccountStatus.ACTIVE.value)

        if state == EFTShortnameState.UNLINKED.value:
            query = query.filter(EFTShortnameModel.auth_account_id.is_(None))
        if state == EFTShortnameState.LINKED.value:
            query = query.filter(EFTShortnameModel.auth_account_id.isnot(None))

        return query.all()

    @classmethod
    def _apply_electronic_funds_transfers_to_pending_invoices(cls,
                                                              eft_short_name: EFTShortnameModel,
                                                              payment: PaymentModel) -> float:
        """Apply the electronic funds transfers again."""
        current_app.logger.info(
            f'Applying electronic funds transfer to pending invoices: {eft_short_name.id}')

        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(
            eft_short_name.auth_account_id)

        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)

        invoices: List[InvoiceModel] = EFTShortNamesService.get_invoices_owing(
            eft_short_name.auth_account_id)

        current_app.logger.info(f'Found {len(invoices)} to apply receipt')
        applied_amount = 0
        print('FIRE')
        for invoice in invoices:
            invoice_reference: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
                invoice.id, InvoiceReferenceStatus.ACTIVE.value
            )

            # apply invoice to the CFS_ACCOUNT
            cls.apply_electronic_funds_transfer_to_invoice(
                payment_account, cfs_account, eft_short_name, invoice, invoice_reference.invoice_number, payment
            )

            # IF invoice balance is zero, then update records.
            if CFSService.get_invoice(cfs_account=cfs_account, inv_number=invoice_reference.invoice_number) \
                    .get('amount_due') == 0:
                applied_amount += invoice.total
                invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
                invoice.invoice_status_code = InvoiceStatus.PAID.value
                invoice.payment_date = datetime.now()

        return applied_amount

    @classmethod
    def apply_electronic_funds_transfer_to_invoice(cls,  # pylint: disable = too-many-arguments, too-many-locals
                                                   payment_account: PaymentAccountModel,
                                                   cfs_account: CfsAccountModel,
                                                   eft_short_name: EFTShortnameModel,
                                                   invoice: InvoiceModel,
                                                   invoice_number: str,
                                                   payment: PaymentModel) -> bool:
        """Apply electronic funds transfers (receipts in CFS) to invoice."""
        has_errors = False
        # an invoice has to be applied to multiple receipts (incl. all linked RS); apply till the balance is zero
        try:
            receipt_number = generate_receipt_number(payment.id)
            current_app.logger.debug(f'Apply receipt {receipt_number} on invoice {invoice_number} '
                                     f'for electronic funds transfer {eft_short_name.id}')

            # If balance of receipt is zero, continue to next receipt.
            receipt_balance_before_apply = float(
                CFSService.get_receipt(cfs_account, receipt_number).get('unapplied_amount')
            )
            current_app.logger.debug(f'Current balance on {receipt_number} = {receipt_balance_before_apply}')
            if receipt_balance_before_apply == 0:
                current_app.logger.debug(f'Applying receipt {receipt_number} to {invoice_number}')
                receipt_response = CFSService.apply_receipt(cfs_account, receipt_number, invoice_number)

                receipt = Receipt()
                receipt.receipt_number = receipt_response.json().get('receipt_number', None)
                receipt_amount = receipt_balance_before_apply - float(receipt_response.json().get('unapplied_amount'))
                receipt.receipt_amount = receipt_amount
                receipt.invoice_id = invoice.id
                receipt.receipt_date = datetime.now()
                receipt.flush()

                invoice_from_cfs = CFSService.get_invoice(cfs_account, invoice_number)
                if invoice_from_cfs.get('amount_due') == 0:
                    has_errors = True
                    return has_errors

        except Exception as e:  # NOQA # pylint: disable=broad-except
            capture_message(
                f'Error on creating electronic funds transfer invoice: account id={payment_account.id}, '
                f'electronic funds transfer : {eft_short_name.id}, ERROR : {str(e)}', level='error')
            current_app.logger.error(e)
            has_errors = True

        return has_errors
