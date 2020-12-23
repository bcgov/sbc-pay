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

from typing import List

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import CfsAccountStatus, InvoiceStatus, PaymentMethod, PaymentStatus
from sentry_sdk import capture_message


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

    @classmethod
    def _create_pad_invoices(cls):  # pylint: disable=too-many-locals
        """Create PAD invoices in to CFS system."""
        # Find all accounts which have done a transaction with PAD transactions

        inv_subquery = db.session.query(InvoiceModel.payment_account_id) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value) \
            .filter(InvoiceModel.invoice_status_code == PaymentStatus.CREATED.value).subquery()

        # Exclude the accounts which are in FREEZE state.
        pad_accounts: List[PaymentAccountModel] = db.session.query(PaymentAccountModel) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .filter(CfsAccountModel.status != CfsAccountStatus.FREEZE.value) \
            .filter(PaymentAccountModel.id.in_(inv_subquery)).all()

        current_app.logger.info(f'Found {len(pad_accounts)} with PAD transactions.')

        for account in pad_accounts:
            # Find all PAD invoices for this account
            account_invoices = db.session.query(InvoiceModel) \
                .filter(InvoiceModel.payment_account_id == account.id) \
                .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value) \
                .filter(InvoiceModel.invoice_status_code == InvoiceStatus.CREATED.value) \
                .order_by(InvoiceModel.created_on.desc()).all()

            # Get cfs account
            payment_account: PaymentAccountService = PaymentAccountService.find_by_id(account.id)

            current_app.logger.debug(
                f'Found {len(account_invoices)} invoices for account {payment_account.auth_account_id}')
            if len(account_invoices) == 0:
                continue

            # If the CFS Account status is not ACTIVE, raise error and continue
            if payment_account.cfs_account_status not in \
                    (CfsAccountStatus.ACTIVE.value, CfsAccountStatus.INACTIVE.value):
                capture_message(f'CFS Account status is not ACTIVE. for account {payment_account.auth_account_id} '
                                f'is {payment_account.cfs_account_status}', level='error')
                current_app.logger.error(f'CFS status for account {payment_account.auth_account_id} '
                                         f'is {payment_account.cfs_account_status}')
                continue

            # Add all lines together
            lines = []
            invoice_total: float = 0
            for invoice in account_invoices:
                lines.append(*invoice.payment_line_items)
                invoice_total += invoice.total

            try:
                # Get the first invoice id as the trx number for CFS
                invoice_response = CFSService.create_account_invoice(transaction_number=account_invoices[0].id,
                                                                     line_items=lines,
                                                                     payment_account=payment_account)
            except Exception as e:  # pylint: disable=broad-except
                capture_message(f'Error on creating PAD invoice: account id={payment_account.id}, '
                                f'auth account : {payment_account.auth_account_id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue

            # Iterate invoice and create invoice reference records
            for invoice in account_invoices:
                # Create invoice reference, payment record and a payment transaction
                InvoiceReference.create(
                    invoice_id=invoice.id,
                    invoice_number=invoice_response.json().get('invoice_number'),
                    reference_number=invoice_response.json().get('pbc_ref_number', None))

                # Misc
                invoice.cfs_account_id = payment_account.cfs_account_id
                invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
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
        invoices = InvoiceModel.query \
            .filter_by(payment_method_code=payment_method.value) \
            .filter_by(invoice_status_code=InvoiceStatus.CREATED.value)\
            .order_by(InvoiceModel.created_on.asc()).all()

        current_app.logger.info(f'Found {len(invoices)} to be created in CFS.')
        for invoice in invoices:
            # Get cfs account
            payment_account: PaymentAccountService = PaymentAccountService.find_by_id(invoice.payment_account_id)

            # Create a CFS invoice
            current_app.logger.debug(f'Creating cfs invoice for invoice {invoice.id}')
            try:
                invoice_response = CFSService.create_account_invoice(transaction_number=invoice.id,
                                                                     line_items=invoice.payment_line_items,
                                                                     payment_account=payment_account)
            except Exception as e:  # pylint: disable=broad-except
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
