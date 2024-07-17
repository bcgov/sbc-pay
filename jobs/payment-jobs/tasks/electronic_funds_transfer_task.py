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
from datetime import datetime, timezone
from typing import List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import (
    CfsAccountStatus, EFTCreditInvoiceStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentSystem,
    ReverseOperation)
from sentry_sdk import capture_message


class ElectronicFundsTransferTask:  # pylint:disable=too-few-public-methods
    """Task to link electronic funds transfers."""

    @classmethod
    def _get_eft_credit_invoice_links_by_status(cls, status: str) \
            -> List[InvoiceModel, EFTCreditInvoiceLinkModel, CfsAccountModel]:
        """Get electronic funds transfer by state."""
        query = db.session.query(InvoiceModel, EFTCreditInvoiceLinkModel, CfsAccountModel) \
            .join(EFTCreditModel, EFTCreditModel.id == EFTCreditInvoiceLinkModel.eft_credit_id) \
            .join(PaymentAccountModel, PaymentAccountModel.id == EFTCreditModel.payment_account_id) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .join(InvoiceModel, InvoiceModel.id == EFTCreditInvoiceLinkModel.invoice_id) \
            .filter(CfsAccountModel.status == CfsAccountStatus.ACTIVE.value) \
            .filter(CfsAccountModel.payment_method == PaymentMethod.EFT.value) \
            .filter(EFTCreditInvoiceLinkModel.status_code == status)
        if status == EFTCreditInvoiceStatus.PENDING.value:
            query = query.filter(InvoiceModel.disbursement_status_code.is_(None))
        return query.order_by(InvoiceModel.payment_account_id, EFTCreditInvoiceLinkModel.id).all()

    @classmethod
    def _apply_eft_receipt_to_invoice(cls,
                                      cfs_account: CfsAccountModel,
                                      invoice_reference: InvoiceReferenceModel,
                                      receipt_number,
                                      amount) -> bool:
        """Apply electronic funds transfers (receipts in CFS) to invoice."""
        CFSService.apply_receipt(cfs_account, receipt_number, invoice_reference.invoice_number)
        ReceiptModel(receipt_number=receipt_number,
                     receipt_amount=amount,
                     invoice_id=invoice_reference.invoice_id,
                     receipt_date=datetime.now(tz=timezone.utc)).flush()

    @classmethod
    def link_electronic_funds_transfers_cfs(cls):
        """Replicate linked EFT's as receipts inside of CFS and mark invoices as paid."""
        credit_invoice_links = cls._get_eft_credit_invoice_links_by_status(EFTCreditInvoiceStatus.PENDING.value)
        for invoice, credit_invoice_link, cfs_account in credit_invoice_links:
            try:
                current_app.logger.debug(f'Create EFT Invoice Links in CFS - PayAccount: {invoice.payment_account_id}'
                                         f'Id: {credit_invoice_link.id} - Amount: {credit_invoice_link.amount} '
                                         f'- Invoice Id: {invoice.id}')
                invoice_reference = InvoiceReferenceModel.find_by_invoice_id_and_status(
                    credit_invoice_link.invoice_id, InvoiceReferenceStatus.ACTIVE.value
                )
                invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
                invoice_reference.flush()
                # Note: Not creating the entire EFT as a receipt because it can be mapped to multiple CFS accounts.
                # eft_credit_invoice_links table should reflect exactly what's in CAS.
                receipt_number = f'EFT-CIL-{credit_invoice_link.id}'
                CFSService.create_cfs_receipt(
                    cfs_account=cfs_account,
                    rcpt_number=receipt_number,
                    rcpt_date=credit_invoice_link.created_on.strftime('%Y-%m-%d'),
                    amount=credit_invoice_link.amount,
                    payment_method=PaymentMethod.EFT.value,
                    access_token=CFSService.get_token(PaymentSystem.FAS).json().get('access_token'))
                cls._apply_eft_receipt_to_invoice(
                    cfs_account, invoice_reference, receipt_number, credit_invoice_link.amount)
                invoice.invoice_status_code = InvoiceStatus.PAID.value
                invoice.paid = credit_invoice_link.amount
                invoice.payment_date = datetime.now(tz=timezone.utc)
                invoice.flush()
                credit_invoice_link.status_code = EFTCreditInvoiceStatus.COMPLETED.value
                credit_invoice_link.flush()
                db.session.commit()
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on linking EFT invoice links in CFS '
                    f'Account id={invoice.payment_account_id} '
                    f'EFT Credit invoice Link : {credit_invoice_link.id}'
                    f'ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                db.session.rollback()
                continue

    @classmethod
    def reverse_electronic_funds_transfers_cfs(cls):
        """Reverse electronic funds transfers receipts in CFS and reset invoices."""
        credit_invoice_links = cls._get_eft_credit_invoice_links_by_status(EFTCreditInvoiceStatus.PENDING_REFUND.value)
        for invoice, credit_invoice_link, cfs_account in credit_invoice_links:
            try:
                current_app.logger.debug(f'Reverse EFT Invoice Links in CFS - PayAccount: {invoice.payment_account_id}'
                                         f'Id: {credit_invoice_link.id} - Amount: {credit_invoice_link.amount}'
                                         f'- Invoice Id: {invoice.id}')
                receipt_number = f'EFT-CIL-{credit_invoice_link.id}'
                invoice_reference = InvoiceReferenceModel.find_by_invoice_id_and_status(
                    invoice.id, InvoiceReferenceStatus.COMPLETED.value
                )
                invoice_reference.status_code = InvoiceReferenceStatus.ACTIVE.value
                invoice_reference.flush()
                CFSService.reverse_rs_receipt_in_cfs(cfs_account, receipt_number, ReverseOperation.VOID.value)
                invoice.invoice_status_code = InvoiceStatus.CREATED.value
                invoice.paid = 0
                invoice.refunded = credit_invoice_link.amount
                invoice.refund_date = datetime.now(tz=timezone.utc)
                invoice.flush()
                for receipt in ReceiptModel.find_all_receipts_for_invoice(invoice.id):
                    db.session.delete(receipt)
                credit_invoice_link.status_code = EFTCreditInvoiceStatus.REFUNDED.value
                credit_invoice_link.flush()
                db.session.commit()
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on reversing EFT invoice links in CFS '
                    f'Account id={invoice.payment_account_id} '
                    f'EFT Credit invoice Link : {credit_invoice_link.id}'
                    f'ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                db.session.rollback()
                continue
