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
from datetime import datetime
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
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment import Payment
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.services.receipt import Receipt
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem)
from sentry_sdk import capture_message

from utils import mailer


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
        cls._create_pad_invoices()
        cls._create_online_banking_invoices()
        cls._create_eft_invoices()
        cls._create_wire_invoices()
        cls._create_rs_invoices()
        # Cancel invoice is the only non-creation of invoice in this job.
        cls._cancel_rs_invoices()

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
            current_app.logger.debug(f'Creating cfs invoice for invoice {invoice.id}')
            routing_slip = RoutingSlipModel.find_by_number(invoice.routing_slip)
            routing_slip_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                routing_slip.payment_account_id)
            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                routing_slip_payment_account.id)
            invoice_reference = InvoiceReferenceModel.find_any_active_reference_by_invoice_number(invoice.id)
            try:
                # find receipts against the invoice and unapply
                # apply receipt now
                receipts: List[ReceiptModel] = ReceiptModel.find_all_receipts_for_invoice(invoice_id=invoice.id)
                for receipt in receipts:
                    CFSService.unapply_receipt(cfs_account, receipt.receipt_number,
                                               invoice_reference.json().get('invoice_number', None))

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

            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
            invoice_reference.status_code = InvoiceReferenceStatus.CANCELLED.value
            invoice.save()

    @classmethod
    def _create_rs_invoices(cls):  # pylint: disable=too-many-locals
        """Create RS invoices in to CFS system."""
        # Find all pending routing slips.

        # find all routing slip invoices [cash or cheque]
        # create invoices in csf
        # do the recipt apply
        invoices: List[InvoiceModel] = InvoiceModel.query \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.INTERNAL.value) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value) \
            .filter(InvoiceModel.routing_slip is not None) \
            .order_by(InvoiceModel.created_on.asc()).all()

        current_app.logger.info(f'Found {len(invoices)} to be created in CFS.')
        receipt_response = {}
        for invoice in invoices:
            # Create a CFS invoice
            has_any_error_in_cfs_creation = False
            current_app.logger.debug(f'Creating cfs invoice for invoice {invoice.id}')
            routing_slip = RoutingSlipModel.find_by_number(invoice.routing_slip)
            routing_slip_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                routing_slip.payment_account_id)

            # apply invoice to the active CFS_ACCOUNT which will be the parent routing slip
            active_cfs_account = CfsAccountModel.find_effective_by_account_id(
                routing_slip_payment_account.id)

            invoice_response = CFSService.create_account_invoice(transaction_number=invoice.id,
                                                                 line_items=invoice.payment_line_items,
                                                                 cfs_account=active_cfs_account)
            invoice_number = invoice_response.json().get('invoice_number', None)
            routing_slips: List[RoutingSlipModel] = RoutingSlipModel. \
                find_all_by_payment_account_id(routing_slip_payment_account.id)
            # an invoice has to be applied to multiple receipts ; apply till the balance is zero
            for routing_slip in routing_slips:
                try:
                    # apply receipt now
                    current_app.logger.debug(f'Apply receipt {routing_slip.number} on invoice {invoice_number} '
                                             f'for routing slip {routing_slip.number}')

                    routing_slip_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                        routing_slip.payment_account_id)

                    cfs_account = CfsAccountModel.find_effective_by_account_id(
                        routing_slip_payment_account.id)

                    receipt_response = CFSService.apply_receipt(cfs_account, routing_slip.number,
                                                                invoice_number)

                    # Create receipt.
                    receipt = Receipt()
                    receipt.receipt_number = receipt_response.json().get('receipt_number', None)
                    # TODO verify if paybc response has a dollar
                    receipt_amount = receipt_response.json().get('receipt_amount', None)
                    receipt.receipt_amount = receipt_amount
                    receipt.invoice_id = invoice.id
                    receipt.receipt_date = datetime.now()
                    receipt.flush()

                    invoice_from_cfs = CFSService.get_invoice(active_cfs_account, invoice_number)
                    if invoice_from_cfs.get('amount_due') <= 0:
                        break

                except Exception as e:  # NOQA # pylint: disable=broad-except
                    capture_message(
                        f'Error on creating Routing Slip invoice: account id={routing_slip_payment_account.id}, '
                        f'routing slip : {routing_slip.id}, ERROR : {str(e)}', level='error')
                    current_app.logger.error(e)
                    has_any_error_in_cfs_creation = True
                    continue

            if has_any_error_in_cfs_creation:
                # move on to next invoice
                continue

            invoice_reference: InvoiceReference = InvoiceReference.create(
                invoice.id, invoice_number,
                # TODO is pbc_ref_number correct?
                invoice_response.json().get('pbc_ref_number', None))

            current_app.logger.debug('>create_invoice')
            # leave the status as PAID
            invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
            invoice.invoice_status_code = InvoiceStatus.PAID.value
            invoice.paid = invoice.total

            Payment.create(payment_method=PaymentMethod.INTERNAL.value,
                           payment_system=PaymentSystem.INTERNAL.value,
                           payment_status=PaymentStatus.COMPLETED.value,
                           invoice_number=invoice_reference.invoice_number,
                           invoice_amount=invoice.total,
                           payment_account_id=invoice.payment_account_id)
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
            .filter(PaymentAccountModel.id.in_(inv_subquery)).all()

        current_app.logger.info(f'Found {len(pad_accounts)} with PAD transactions.')

        invoice_ref_subquery = db.session.query(InvoiceReferenceModel.invoice_id). \
            filter(InvoiceReferenceModel.status_code.in_((InvoiceReferenceStatus.ACTIVE.value,)))

        for account in pad_accounts:
            # Find all PAD invoices for this account
            account_invoices = db.session.query(InvoiceModel) \
                .filter(InvoiceModel.payment_account_id == account.id) \
                .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value) \
                .filter(InvoiceModel.invoice_status_code == InvoiceStatus.APPROVED.value) \
                .filter(InvoiceModel.id.notin_(invoice_ref_subquery)) \
                .order_by(InvoiceModel.created_on.desc()).all()

            # Get cfs account
            payment_account: PaymentAccountService = PaymentAccountService.find_by_id(account.id)

            current_app.logger.debug(
                f'Found {len(account_invoices)} invoices for account {payment_account.auth_account_id}')
            if len(account_invoices) == 0:
                continue

            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)
            if cfs_account is None:
                # Get the last invoice and look up cfs_account for it, as the account might have got upgraded.
                cfs_account = CfsAccountModel.find_by_id(account_invoices[0].cfs_account_id)

            # If the CFS Account status is not ACTIVE, raise error and continue
            if cfs_account.status not in (CfsAccountStatus.ACTIVE.value, CfsAccountStatus.INACTIVE.value):
                capture_message(f'CFS Account status is not ACTIVE. for account {payment_account.auth_account_id} '
                                f'is {payment_account.cfs_account_status}', level='error')
                current_app.logger.error(f'CFS status for account {payment_account.auth_account_id} '
                                         f'is {payment_account.cfs_account_status}')
                continue

            # Add all lines together
            lines = []
            invoice_total: float = 0
            for invoice in account_invoices:
                lines.extend(invoice.payment_line_items)
                invoice_total += invoice.total

            try:
                # Get the first invoice id as the trx number for CFS
                invoice_response = CFSService.create_account_invoice(transaction_number=account_invoices[-1].id,
                                                                     line_items=lines,
                                                                     cfs_account=cfs_account)
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(f'Error on creating PAD invoice: account id={payment_account.id}, '
                                f'auth account : {payment_account.auth_account_id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue
            # emit account mailer event
            mailer.publish_mailer_events('pad.invoiceCreated', payment_account, {'invoice_total': invoice_total})
            # Iterate invoice and create invoice reference records
            for invoice in account_invoices:
                # Create invoice reference, payment record and a payment transaction
                InvoiceReference.create(
                    invoice_id=invoice.id,
                    invoice_number=invoice_response.json().get('invoice_number'),
                    reference_number=invoice_response.json().get('pbc_ref_number', None))

                # Misc
                invoice.cfs_account_id = payment_account.cfs_account_id
                # no longer set to settlement sceduled
                # invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
                invoice.save()

    @classmethod
    def _create_online_banking_invoices(cls):
        """Create online banking invoices to CFS system."""
        cls._create_single_invoice_per_purchase(PaymentMethod.ONLINE_BANKING)

    @classmethod
    def _create_eft_invoices(cls):
        """Create EFT invoices to CFS system."""
        cls._create_single_invoice_per_purchase(PaymentMethod.EFT)

    @classmethod
    def _create_wire_invoices(cls):
        """Create Wire invoices to CFS system."""
        cls._create_single_invoice_per_purchase(PaymentMethod.WIRE)

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
                invoice_number=invoice_response.json().get('invoice_number'),
                reference_number=invoice_response.json().get('pbc_ref_number', None))

            # Misc
            invoice.cfs_account_id = payment_account.cfs_account_id
            # leave the status as SETTLEMENT_SCHEDULED
            invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
            invoice.save()
