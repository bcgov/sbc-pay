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
from dataclasses import dataclass
from decimal import Decimal
from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTShortnamesHistorical as EFTShortnameHistoryModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.utils.enums import (
    CfsAccountStatus, DisbursementStatus, EFTCreditInvoiceStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod,
    PaymentStatus, PaymentSystem, ReverseOperation)
from sentry_sdk import capture_message
from sqlalchemy import func, or_
from sqlalchemy.orm import lazyload, registry

from utils.auth_event import AuthEvent


class EFTTask:  # pylint:disable=too-few-public-methods
    """Task to link electronic funds transfers."""

    history_group_ids = set()
    overdue_account_ids = {}

    @classmethod
    def get_eft_credit_invoice_links_by_status(cls, status: str) \
            -> List[tuple[InvoiceModel, EFTCreditInvoiceLinkModel, CfsAccountModel]]:
        """Get electronic funds transfer by state."""
        latest_cfs_account = db.session.query(func.max(CfsAccountModel.id).label('max_id_per_payment_account')) \
            .filter(CfsAccountModel.payment_method == PaymentMethod.EFT.value) \
            .filter(CfsAccountModel.status == CfsAccountStatus.ACTIVE.value) \
            .group_by(CfsAccountModel.account_id).subquery('latest_cfs_account')

        cil_rollup = db.session.query(func.min(EFTCreditInvoiceLinkModel.id).label('id'),
                                      EFTCreditInvoiceLinkModel.invoice_id,
                                      EFTCreditInvoiceLinkModel.status_code,
                                      EFTCreditInvoiceLinkModel.receipt_number,
                                      func.array_agg(EFTCreditInvoiceLinkModel.id)  # pylint: disable=not-callable
                                      .label('link_ids'),
                                      func.sum(EFTCreditInvoiceLinkModel.amount).label('rollup_amount')) \
            .join(InvoiceReferenceModel, InvoiceReferenceModel.invoice_id == EFTCreditInvoiceLinkModel.invoice_id) \
            .filter(EFTCreditInvoiceLinkModel.status_code == status) \
            .group_by(EFTCreditInvoiceLinkModel.invoice_id,
                      EFTCreditInvoiceLinkModel.status_code,
                      EFTCreditInvoiceLinkModel.receipt_number) \
            .subquery()

        @dataclass
        class EFTCILRollup:
            """Dataclass for rollup so we don't use a tuple instead."""

            invoice_id: int
            status_code: str
            receipt_number: str
            link_ids: List[int]
            rollup_amount: Decimal

        registry().map_imperatively(EFTCILRollup, cil_rollup, primary_key=[cil_rollup.c.invoice_id,
                                                                           cil_rollup.c.status_code,
                                                                           cil_rollup.c.receipt_number])

        query = db.session.query(InvoiceModel, CfsAccountModel, EFTCILRollup) \
            .join(cil_rollup, InvoiceModel.id == cil_rollup.c.invoice_id) \
            .join(CfsAccountModel, CfsAccountModel.account_id == InvoiceModel.payment_account_id) \
            .join(latest_cfs_account, CfsAccountModel.id == latest_cfs_account.c.max_id_per_payment_account) \
            .options(lazyload('*')) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .filter(InvoiceModel.total == cil_rollup.c.rollup_amount)

        match status:
            case EFTCreditInvoiceStatus.PENDING.value:
                query = query.filter(InvoiceModel.disbursement_status_code.is_(None))
                query = query.filter(InvoiceModel.invoice_status_code.in_([InvoiceStatus.APPROVED.value,
                                                                           InvoiceStatus.OVERDUE.value]))
            case EFTCreditInvoiceStatus.PENDING_REFUND.value:
                query = query.filter(or_(InvoiceModel.disbursement_status_code.is_(
                    None), InvoiceModel.disbursement_status_code == DisbursementStatus.COMPLETED.value))
                query = query.filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            case _:
                pass
        return query.order_by(InvoiceModel.payment_account_id, cil_rollup.c.invoice_id).all()

    @classmethod
    def link_electronic_funds_transfers_cfs(cls) -> dict:
        """Replicate linked EFT's as receipts inside of CFS and mark invoices as paid."""
        target_status = EFTCreditInvoiceStatus.PENDING.value
        credit_invoice_links = cls.get_eft_credit_invoice_links_by_status(target_status)
        cls.history_group_ids = set()
        for invoice, cfs_account, cil_rollup in credit_invoice_links:
            try:
                current_app.logger.info(f'PayAccount: {invoice.payment_account_id} Id: {cil_rollup.id} -'
                                        f' Invoice Id: {invoice.id} - Amount: {cil_rollup.rollup_amount}')
                receipt_number = f'EFTCIL{cil_rollup.id}'
                if invoice.invoice_status_code == InvoiceStatus.OVERDUE.value:
                    cls.overdue_account_ids[invoice.payment_account_id] = cfs_account.payment_account
                cls._create_receipt_and_invoice(cfs_account, cil_rollup, invoice, receipt_number)
                cls._update_cil_and_shortname_history(cil_rollup, receipt_number=receipt_number)
                db.session.commit()
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on linking EFT invoice links in CFS '
                    f'Account id={invoice.payment_account_id} '
                    f'EFT Credit invoice Link : {cil_rollup.id}'
                    f'ERROR : {str(e)}', level='error')
                current_app.logger.error(f'Error Account id={invoice.payment_account_id} - '
                                         f'EFT Credit invoice Link : {cil_rollup.id}', exc_info=True)
                db.session.rollback()
                continue
        cls.unlock_overdue_accounts()

    @classmethod
    def reverse_electronic_funds_transfers_cfs(cls):
        """Reverse electronic funds transfers receipts in CFS and reset invoices."""
        target_status = EFTCreditInvoiceStatus.PENDING_REFUND.value
        credit_invoice_links = cls.get_eft_credit_invoice_links_by_status(target_status)
        cls.history_group_ids = set()
        for invoice, cfs_account, cil_rollup in credit_invoice_links:
            try:
                current_app.logger.info(f'PayAccount: {invoice.payment_account_id} Id: {cil_rollup.id} -'
                                        f' Invoice Id: {invoice.id} - Amount: {cil_rollup.rollup_amount}')
                receipt_number = cil_rollup.receipt_number
                cls._rollback_receipt_and_invoice(cfs_account, invoice, receipt_number)
                cls._update_cil_and_shortname_history(cil_rollup)
                db.session.commit()
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on reversing EFT invoice links in CFS '
                    f'Account id={invoice.payment_account_id} '
                    f'EFT Credit invoice Link : {cil_rollup.id}'
                    f'ERROR : {str(e)}', level='error')
                current_app.logger.error(f'Error Account id={invoice.payment_account_id} - '
                                         f'EFT Credit invoice Link : {cil_rollup.id}', exc_info=True)
                db.session.rollback()
                continue

    @classmethod
    def unlock_overdue_accounts(cls):
        """Check and unlock overdue EFT accounts."""
        for (payment_account_id, payment_account) in cls.overdue_account_ids.items():
            if InvoiceService.has_overdue_invoices(payment_account_id):
                continue
            payment_account.has_overdue_invoices = None
            payment_account.save()
            AuthEvent.publish_unlock_account_event(payment_account)

    @classmethod
    def _get_eft_history_by_group_id(cls, related_group_id: int) -> EFTShortnameHistoryModel:
        """Get EFT short name historical record by related group id."""
        return (db.session.query(EFTShortnameHistoryModel)
                .filter(EFTShortnameHistoryModel.related_group_link_id == related_group_id)).one_or_none()

    @classmethod
    def _finalize_shortname_history(cls, group_set: set, invoice_link: EFTCreditInvoiceLinkModel):
        """Finalize EFT short name historical record state."""
        if invoice_link.link_group_id is None or invoice_link.link_group_id in group_set:
            return

        group_set.add(invoice_link.link_group_id)
        if history_model := cls._get_eft_history_by_group_id(invoice_link.link_group_id):
            history_model.hidden = False
            history_model.is_processing = False
            history_model.flush()

    @classmethod
    def _update_cil_and_shortname_history(cls, cil_rollup, receipt_number=None):
        """Update electronic invoice links."""
        cils = db.session.query(EFTCreditInvoiceLinkModel).filter(
            EFTCreditInvoiceLinkModel.id.in_(cil_rollup.link_ids)).all()
        for cil in cils:
            cil.status_code = EFTCreditInvoiceStatus.COMPLETED.value if receipt_number \
                     else EFTCreditInvoiceStatus.REFUNDED.value
            cil.receipt_number = receipt_number or cil.receipt_number
            cil.flush()
            cls._finalize_shortname_history(cls.history_group_ids, cil)

    @classmethod
    def _create_receipt_and_invoice(cls,
                                    cfs_account: CfsAccountModel,
                                    cil_rollup: EFTCreditInvoiceLinkModel,
                                    invoice: InvoiceModel,
                                    receipt_number: str):
        """Create receipt in CFS and marks invoice as paid, with payment and receipt rows."""
        if not (invoice_reference := InvoiceReferenceModel.find_by_invoice_id_and_status(
            cil_rollup.invoice_id, InvoiceReferenceStatus.ACTIVE.value
        )):
            raise Exception(f'Active Invoice reference not '  # pylint: disable=broad-exception-raised
                            f'found for invoice id: {invoice.id}')
        invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
        invoice_reference.flush()
        # Note: Not creating the entire EFT as a receipt because it can be mapped to multiple CFS accounts.
        # eft_credit_invoice_links table should reflect exactly what's in CAS.
        CFSService.create_cfs_receipt(
            cfs_account=cfs_account,
            rcpt_number=receipt_number,
            rcpt_date=datetime.now(tz=timezone.utc).strftime('%Y-%m-%d'),
            amount=cil_rollup.rollup_amount,
            payment_method=PaymentMethod.EFT.value,
            access_token=CFSService.get_token(PaymentSystem.FAS).json().get('access_token'))
        CFSService.apply_receipt(cfs_account, receipt_number, invoice_reference.invoice_number)
        ReceiptModel(receipt_number=receipt_number,
                     receipt_amount=cil_rollup.rollup_amount,
                     invoice_id=invoice_reference.invoice_id,
                     receipt_date=datetime.now(tz=timezone.utc)).flush()
        PaymentModel(payment_method_code=PaymentMethod.EFT.value,
                     payment_status_code=PaymentStatus.COMPLETED.value,
                     payment_system_code=PaymentSystem.PAYBC.value,
                     invoice_number=invoice.id,
                     invoice_amount=invoice.total,
                     payment_account_id=cfs_account.account_id,
                     payment_date=datetime.now(tz=timezone.utc),
                     paid_amount=cil_rollup.rollup_amount,
                     receipt_number=receipt_number).flush()
        invoice.invoice_status_code = InvoiceStatus.PAID.value
        invoice.paid = cil_rollup.rollup_amount
        invoice.payment_date = datetime.now(tz=timezone.utc)
        invoice.flush()

    @classmethod
    def _rollback_receipt_and_invoice(cls, cfs_account: CfsAccountModel, invoice: InvoiceModel, receipt_number: str):
        """Rollback receipt in CFS and reset invoice status."""
        if not (invoice_reference := InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice.id, InvoiceReferenceStatus.COMPLETED.value
        )):
            raise Exception(f'Completed invoice reference '  # pylint: disable=broad-exception-raised
                            f'not found for invoice id: {invoice.id}')
        CFSService.reverse_rs_receipt_in_cfs(cfs_account, receipt_number, ReverseOperation.VOID.value)

        if invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value:
            invoice_reference.status_code = InvoiceReferenceStatus.CANCELLED.value
            adjustment_negative_amount = -invoice.total
            # TODO: I don't think this will work because it's rolled up, we need to actually adjust the invoice
            # Because it wont be adjusted to zero, it could have left over
            CFSService.adjust_invoice(cfs_account=cfs_account,
                                      inv_number=invoice_reference.invoice_number,
                                      amount=adjustment_negative_amount)
            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
            invoice.refund_date = datetime.now(tz=timezone.utc)
            invoice.refund = invoice.paid
        else:
            invoice_reference.status_code = InvoiceReferenceStatus.ACTIVE.value
            invoice.paid = 0
            invoice.payment_date = None
            invoice.invoice_status_code = InvoiceStatus.APPROVED.value
        invoice_reference.flush()
        invoice.flush()
        if payment := PaymentModel.find_payment_for_invoice(invoice.id):
            db.session.delete(payment)
        for receipt in ReceiptModel.find_all_receipts_for_invoice(invoice.id):
            db.session.delete(receipt)
