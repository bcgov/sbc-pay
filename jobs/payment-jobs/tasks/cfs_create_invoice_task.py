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
"""Task to create CFS invoices offline."""
from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.services import EftService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment import Payment
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem)
from pay_api.utils.util import generate_transaction_number
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message
from sqlalchemy import select

from utils import mailer

from .routing_slip_task import RoutingSlipTask


class CreateInvoiceTask:  # pylint:disable=too-few-public-methods
    """Task to create invoices in CFS."""

    @classmethod
    def create_invoices(cls):
        """Create invoice in CFS.

        Steps:
        1. Find all invoices from invoice table for Online Banking.
        1.1. Create invoice in CFS for each of those invoices.
        2. Find all invoices from invoice table for PAD payment accounts.
        2.1 Roll up all transactions and create one invoice in CFS.
        3. Update the invoice status as IN TRANSIT
        """
        current_app.logger.info('<< Starting PAD Invoice Creation')
        cls._create_pad_invoices()
        current_app.logger.info('>> Done PAD Invoice Creation')

        current_app.logger.info('<< Starting EFT Invoice Creation')
        cls._create_eft_invoices()
        current_app.logger.info('>> Done EFT Invoice Creation')

        current_app.logger.info('<< Starting Online Banking Invoice Creation')
        cls._create_online_banking_invoices()
        current_app.logger.info('>> Done Online Banking Invoice Creation')

        # Cancel invoice is the only non-creation of invoice in this job.
        current_app.logger.info('<< Starting CANCEL Routing Slip Invoices')
        cls._cancel_rs_invoices()
        current_app.logger.info('>> Done CANCEL Routing Slip Invoices')

        # Cancel first then create, else receipt apply would fail.
        current_app.logger.info('<< Starting Routing Slip Invoice Creation')
        cls._create_rs_invoices()
        current_app.logger.info('>> Done Routing Slip Invoice Creation')

    @classmethod
    def _cancel_rs_invoices(cls):
        """Cancel routing slip invoices in CFS."""
        invoices: List[InvoiceModel] = InvoiceModel.query \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.INTERNAL.value) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value) \
            .filter(InvoiceModel.routing_slip is not None) \
            .order_by(InvoiceModel.created_on.asc()).all()

        current_app.logger.info(f'Found {len(invoices)} to be cancelled in CFS.')
        for invoice in invoices:
            # call unapply rcpts
            # adjust invoice to zero
            current_app.logger.debug(f'Calling the invoice {invoice.id}')
            routing_slip = RoutingSlipModel.find_by_number(invoice.routing_slip)
            routing_slip_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                routing_slip.payment_account_id)
            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                routing_slip_payment_account.id)
            # Find COMPLETED invoice reference; as unapply has to be done only if invoice is created and applied in CFS.
            invoice_reference = InvoiceReferenceModel. \
                find_by_invoice_id_and_status(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value)
            if invoice_reference:
                current_app.logger.debug(f'Found invoice reference - {invoice_reference.invoice_number}')
                try:
                    # find receipts against the invoice and unapply
                    # apply receipt now
                    receipts: List[ReceiptModel] = ReceiptModel.find_all_receipts_for_invoice(invoice_id=invoice.id)
                    for receipt in receipts:
                        CFSService.unapply_receipt(cfs_account, receipt.receipt_number,
                                                   invoice_reference.invoice_number)

                    adjustment_negative_amount = -invoice.total
                    CFSService.adjust_invoice(cfs_account=cfs_account,
                                              inv_number=invoice_reference.invoice_number,
                                              amount=adjustment_negative_amount)

                except Exception as e:  # NOQA # pylint: disable=broad-except
                    capture_message(
                        f'Error on canelling Routing Slip invoice: invoice id={invoice.id}, '
                        f'routing slip : {routing_slip.id}, ERROR : {str(e)}', level='error')
                    current_app.logger.error(e)
                    # TODO stop execution ? what should be the invoice stats ; should we set it to error or retry?
                    continue

                invoice_reference.status_code = InvoiceReferenceStatus.CANCELLED.value

            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
            invoice.refund_date = datetime.now()
            invoice.save()

    @classmethod
    def _create_rs_invoices(cls):  # pylint: disable=too-many-locals
        """Create RS invoices in to CFS system."""
        # Find all pending routing slips.

        # find all routing slip invoices [cash or cheque]
        # create invoices in csf
        # do the receipt apply
        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .join(RoutingSlipModel, RoutingSlipModel.number == InvoiceModel.routing_slip) \
            .join(CfsAccountModel, CfsAccountModel.account_id == RoutingSlipModel.payment_account_id) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.INTERNAL.value) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value) \
            .filter(CfsAccountModel.status.in_([CfsAccountStatus.ACTIVE.value, CfsAccountStatus.FREEZE.value])) \
            .filter(InvoiceModel.routing_slip is not None) \
            .order_by(InvoiceModel.created_on.asc()).all()

        current_app.logger.info(f'Found {len(invoices)} to be created in CFS.')

        for invoice in invoices:
            # Create a CFS invoice
            current_app.logger.debug(f'Creating cfs invoice for invoice {invoice.id}')
            routing_slip = RoutingSlipModel.find_by_number(invoice.routing_slip)
            # If routing slip is not found in Pay-DB, assume legacy RS and move on to next one.
            if not routing_slip:
                continue

            routing_slip_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                routing_slip.payment_account_id)

            # apply invoice to the active CFS_ACCOUNT which will be the parent routing slip
            active_cfs_account = CfsAccountModel.find_effective_by_account_id(routing_slip_payment_account.id)

            try:
                invoice_response = CFSService.create_account_invoice(transaction_number=invoice.id,
                                                                     line_items=invoice.payment_line_items,
                                                                     cfs_account=active_cfs_account)
            except Exception as e:  # NOQA # pylint: disable=broad-except
                # There is a chance that the error is a timeout from CAS side,
                # so to make sure we are not missing any data, make a GET call for the invoice we tried to create
                # and use it if it got created.
                current_app.logger.info(e)  # INFO is intentional as sentry alerted only after the following try/catch
                has_invoice_created: bool = False
                try:
                    # add a 10 seconds delay here as safe bet, as CFS takes time to create the invoice and
                    # since this is a job, delay doesn't cause any performance issue
                    time.sleep(10)
                    invoice_number = generate_transaction_number(str(invoice.id))
                    invoice_response = CFSService.get_invoice(
                        cfs_account=active_cfs_account, inv_number=invoice_number
                    )
                    has_invoice_created = invoice_response.get('invoice_number', None) == invoice_number
                except Exception as exc:  # NOQA # pylint: disable=broad-except,unused-variable
                    # Ignore this error, as it is irrelevant and error on outer level is relevant.
                    pass

                # If no invoice is created raise an error for sentry
                if not has_invoice_created:
                    capture_message(f'Error on creating routing slip invoice: account id={invoice.payment_account.id}, '
                                    f'auth account : {invoice.payment_account.auth_account_id}, ERROR : {str(e)}',
                                    level='error')
                    current_app.logger.error(e)
                    continue

            invoice_number = invoice_response.get('invoice_number', None)

            current_app.logger.info(f'invoice_number  {invoice_number}  created in CFS.')

            has_error_in_apply_receipt = RoutingSlipTask.apply_routing_slips_to_invoice(
                routing_slip_payment_account, active_cfs_account, routing_slip, invoice, invoice_number
            )

            if has_error_in_apply_receipt:
                # move on to next invoice
                continue

            invoice_reference: InvoiceReference = InvoiceReference.create(
                invoice.id, invoice_number,
                invoice_response.get('pbc_ref_number', None))

            current_app.logger.debug('>create_invoice')

            invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value

            Payment.create(payment_method=PaymentMethod.INTERNAL.value,
                           payment_system=PaymentSystem.INTERNAL.value,
                           payment_status=PaymentStatus.COMPLETED.value,
                           invoice_number=invoice_reference.invoice_number,
                           invoice_amount=invoice.total,
                           payment_account_id=invoice.payment_account_id)
            # leave the status as PAID

            invoice.invoice_status_code = InvoiceStatus.PAID.value
            invoice.payment_date = datetime.now()
            invoice.paid = invoice.total
            invoice.save()

    @classmethod
    def _create_pad_invoices(cls):  # pylint: disable=too-many-locals
        """Create PAD invoices in to CFS system."""
        # Find all accounts which have done a transaction with PAD transactions

        inv_subquery = db.session.query(InvoiceModel.payment_account_id) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value).subquery()

        # Exclude the accounts which are in FREEZE state.
        pad_accounts: List[PaymentAccountModel] = db.session.query(PaymentAccountModel) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .filter(CfsAccountModel.status != CfsAccountStatus.FREEZE.value) \
            .filter(PaymentAccountModel.id.in_(select(inv_subquery))).all()

        current_app.logger.info(f'Found {len(pad_accounts)} with PAD transactions.')

        for account in pad_accounts:
            # Find all PAD invoices for this account
            account_invoices = db.session.query(InvoiceModel) \
                .filter(InvoiceModel.payment_account_id == account.id) \
                .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value) \
                .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value) \
                .filter(InvoiceModel.id.notin_(cls._active_invoice_reference_subquery())) \
                .order_by(InvoiceModel.created_on.desc()).all()

            # Get cfs account
            payment_account: PaymentAccountService = PaymentAccountService.find_by_id(account.id)

            if len(account_invoices) == 0:
                continue
            current_app.logger.debug(
                f'Found {len(account_invoices)} invoices for account {payment_account.auth_account_id}')

            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)
            if cfs_account is None:
                # Get the last cfs_account for it, as the account might have got upgraded from PAD to DRAWDOWN.
                cfs_account: CfsAccountModel = CfsAccountModel.query.\
                    filter(CfsAccountModel.account_id == payment_account.id).order_by(CfsAccountModel.id.desc()).first()

            # If the CFS Account status is not ACTIVE or INACTIVE (for above case), raise error and continue
            if cfs_account.status not in (CfsAccountStatus.ACTIVE.value, CfsAccountStatus.INACTIVE.value):
                current_app.logger.info(f'CFS status for account {payment_account.auth_account_id} '
                                        f'is {payment_account.cfs_account_status} skipping.')
                continue

            # Add all lines together
            lines = []
            invoice_total = Decimal('0')
            for invoice in account_invoices:
                lines.extend(invoice.payment_line_items)
                invoice_total += invoice.total
            invoice_number = account_invoices[-1].id
            try:
                # Get the first invoice id as the trx number for CFS
                invoice_response = CFSService.create_account_invoice(transaction_number=invoice_number,
                                                                     line_items=lines,
                                                                     cfs_account=cfs_account)
            except Exception as e:  # NOQA # pylint: disable=broad-except
                # There is a chance that the error is a timeout from CAS side,
                # so to make sure we are not missing any data, make a GET call for the invoice we tried to create
                # and use it if it got created.
                current_app.logger.info(e)  # INFO is intentional as sentry alerted only after the following try/catch
                has_invoice_created: bool = False
                try:
                    # add a 10 seconds delay here as safe bet, as CFS takes time to create the invoice
                    time.sleep(10)
                    invoice_number = generate_transaction_number(str(invoice_number))
                    invoice_response = CFSService.get_invoice(
                        cfs_account=cfs_account, inv_number=invoice_number
                    )
                    has_invoice_created = invoice_response.get('invoice_number', None) == invoice_number
                    invoice_total_matches = Decimal(invoice_response.get('total', '0')) == invoice_total
                except Exception as exc:  # NOQA # pylint: disable=broad-except,unused-variable
                    # Ignore this error, as it is irrelevant and error on outer level is relevant.
                    pass
                # If no invoice is created raise an error for sentry
                if not has_invoice_created:
                    capture_message(f'Error on creating PAD invoice: account id={payment_account.id}, '
                                    f'auth account : {payment_account.auth_account_id}, ERROR : {str(e)}',
                                    level='error')
                    current_app.logger.error(e)
                    continue
                if not invoice_total_matches:
                    capture_message(f'Error on creating PAD invoice: account id={payment_account.id}, '
                                    f'auth account : {payment_account.auth_account_id}, Invoice exists: '
                                    f' CAS total: {invoice_response.get("total", 0)}, PAY-BC total: {invoice_total}',
                                    level='error')
                    current_app.logger.error(e)
                    continue

            additional_params = {
                'invoice_total': float(invoice_total),
                'invoice_process_date': f'{datetime.now()}'
            }
            mailer.publish_mailer_events(QueueMessageTypes.PAD_INVOICE_CREATED.value, payment_account,
                                         additional_params)
            # Iterate invoice and create invoice reference records
            for invoice in account_invoices:
                invoice_reference = InvoiceReferenceModel(
                    invoice_id=invoice.id,
                    invoice_number=invoice_response.get('invoice_number'),
                    reference_number=invoice_response.get('pbc_ref_number', None),
                    status_code=InvoiceReferenceStatus.ACTIVE.value
                )
                db.session.add(invoice_reference)
                invoice.cfs_account_id = cfs_account.id
            db.session.commit()

    @classmethod
    def _return_eft_accounts(cls):
        """Return EFT accounts."""
        invoice_subquery = db.session.query(InvoiceModel.payment_account_id) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value).subquery()

        eft_accounts: List[PaymentAccountModel] = db.session.query(PaymentAccountModel) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .filter(CfsAccountModel.status != CfsAccountStatus.FREEZE.value) \
            .filter(PaymentAccountModel.id.in_(select(invoice_subquery))).all()

        current_app.logger.info(f'Found {len(eft_accounts)} with EFT transactions.')

        return eft_accounts

    @classmethod
    def _save_invoice_reference_records(cls, account_invoices, cfs_account, invoice_response):
        """Save invoice reference records."""
        for invoice in account_invoices:

            invoice_reference = EftService.create_invoice_reference(
                invoice=invoice,
                invoice_number=invoice_response.get('invoice_number'),
                reference_number=invoice_response.get('pbc_ref_number', None)
            )
            db.session.add(invoice_reference)

            invoice.cfs_account_id = cfs_account.id
        db.session.commit()

    @classmethod
    def _active_invoice_reference_subquery(cls):
        return db.session.query(InvoiceReferenceModel.invoice_id). \
            filter(InvoiceReferenceModel.status_code.in_((InvoiceReferenceStatus.ACTIVE.value,)))

    @classmethod
    def _create_eft_invoices(cls):
        """Create EFT invoices in CFS."""
        eft_accounts = cls._return_eft_accounts()

        for eft_account in eft_accounts:
            account_invoices = db.session.query(InvoiceModel) \
                .filter(InvoiceModel.payment_account_id == eft_account.id) \
                .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
                .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value) \
                .filter(InvoiceModel.id.notin_(cls._active_invoice_reference_subquery())) \
                .order_by(InvoiceModel.created_on.desc()).all()

            if not account_invoices:
                continue

            payment_account: PaymentAccountService = PaymentAccountService.find_by_id(eft_account.id)

            if not payment_account:
                continue

            current_app.logger.debug(
                f'Found {len(account_invoices)} invoices for account {payment_account.auth_account_id}')

            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)

            # If no CFS account then the payment method might have changed from EFT to DRAWDOWN
            if not cfs_account:
                cfs_account: CfsAccountModel = CfsAccountModel.query.\
                    filter(CfsAccountModel.account_id == payment_account.id).order_by(CfsAccountModel.id.desc()).first()

            # If CFS account is not ACTIVE or INACTIVE (for above case), raise error and continue
            if cfs_account.status not in (CfsAccountStatus.ACTIVE.value, CfsAccountStatus.INACTIVE.value):
                current_app.logger.info(f'CFS status for account {payment_account.auth_account_id} '
                                        f'is {payment_account.cfs_account_status} skipping.')
                continue

            # Add all payment line items together
            lines = []
            invoice_total = Decimal('0')
            for invoice in account_invoices:
                lines.extend(invoice.payment_line_items)
                invoice_total += invoice.total

            invoice_number = account_invoices[-1].id
            try:
                # Get the first invoice id as the trx number for CFS
                invoice_response = CFSService.create_account_invoice(transaction_number=invoice_number,
                                                                     line_items=lines,
                                                                     cfs_account=cfs_account)
            except Exception as e:  # NOQA # pylint: disable=broad-except
                # There is a chance that the error is a timeout from CAS side,
                # so to make sure we are not missing any data, make a GET call for the invoice we tried to create
                # and use it if it got created.
                current_app.logger.info(e)  # INFO is intentional as sentry alerted only after the following try/catch
                has_invoice_created: bool = False
                try:
                    # add a 10 seconds delay here as safe bet, as CFS takes time to create the invoice
                    time.sleep(10)
                    invoice_number = generate_transaction_number(str(invoice_number))
                    invoice_response = CFSService.get_invoice(
                        cfs_account=cfs_account, inv_number=invoice_number
                    )
                    has_invoice_created = invoice_response.get('invoice_number', None) == invoice_number
                    invoice_total_matches = Decimal(invoice_response.get('total', '0')) == invoice_total
                except Exception as exc:  # NOQA # pylint: disable=broad-except,unused-variable
                    # Ignore this error, as it is irrelevant and error on outer level is relevant.
                    pass
                # If no invoice is created raise an error for sentry
                if not has_invoice_created:
                    capture_message(f'Error on creating EFT invoice: account id={payment_account.id}, '
                                    f'auth account : {payment_account.auth_account_id}, ERROR : {str(e)}',
                                    level='error')
                    current_app.logger.error(e)
                    continue
                if not invoice_total_matches:
                    capture_message(f'Error on creating EFT invoice: account id={payment_account.id}, '
                                    f'auth account : {payment_account.auth_account_id}, Invoice exists: '
                                    f' CAS total: {invoice_response.get("total", 0)}, PAY-BC total: {invoice_total}',
                                    level='error')
                    current_app.logger.error(e)
                    continue

            mailer.publish_mailer_events(QueueMessageTypes.EFT_INVOICE_CREATED.value, payment_account, {
                'invoice_total': float(invoice_total),
                'invoice_process_date': f'{datetime.now(tz=timezone.utc)}'
            })

            cls._save_invoice_reference_records(account_invoices, cfs_account, invoice_response)

    @classmethod
    def _create_online_banking_invoices(cls):
        """Create online banking invoices to CFS system."""
        cls._create_single_invoice_per_purchase(PaymentMethod.ONLINE_BANKING)

    @classmethod
    def _create_single_invoice_per_purchase(cls, payment_method: PaymentMethod):
        """Create one CFS invoice per purchase."""
        invoices: List[InvoiceModel] = InvoiceModel.query \
            .filter_by(payment_method_code=payment_method.value) \
            .filter_by(invoice_status_code=InvoiceStatus.CREATED.value) \
            .order_by(InvoiceModel.created_on.asc()).all()

        current_app.logger.info(f'Found {len(invoices)} to be created in CFS.')
        for invoice in invoices:
            # Get cfs account
            payment_account: PaymentAccountService = PaymentAccountService.find_by_id(invoice.payment_account_id)
            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)

            # Check for corp type and see if online banking is allowed.
            if invoice.payment_method_code == PaymentMethod.ONLINE_BANKING.value:
                corp_type: CorpTypeModel = CorpTypeModel.find_by_code(invoice.corp_type_code)
                if not corp_type.is_online_banking_allowed:
                    continue

            # Create a CFS invoice
            current_app.logger.debug(f'Creating cfs invoice for invoice {invoice.id}')
            try:
                invoice_response = CFSService.create_account_invoice(transaction_number=invoice.id,
                                                                     line_items=invoice.payment_line_items,
                                                                     cfs_account=cfs_account)
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(f'Error on creating Online Banking invoice: account id={payment_account.id}, '
                                f'auth account : {payment_account.auth_account_id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue

            # Create invoice reference, payment record and a payment transaction
            InvoiceReference.create(
                invoice_id=invoice.id,
                invoice_number=invoice_response.get('invoice_number'),
                reference_number=invoice_response.get('pbc_ref_number', None))

            # Misc
            invoice.cfs_account_id = payment_account.cfs_account_id
            # leave the status as SETTLEMENT_SCHEDULED
            invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
            invoice.save()
