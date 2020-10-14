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

from datetime import timedelta

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.online_banking_service import OnlineBankingService
from pay_api.services.pad_service import PadService
from pay_api.services.payment import Payment
from pay_api.utils.constants import CFS_BATCH_SOURCE, CFS_CUST_TRX_TYPE, CFS_LINE_TYPE, CFS_TERM_NAME
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceStatus, PaymentMethod, TransactionStatus
from pay_api.utils.util import current_local_time


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

    @classmethod
    def _create_pad_invoices(cls):  # pylint: disable=too-many-locals
        """Create PAD invoices in to CFS system."""
        # TODO Add date filter
        end_time = current_local_time()
        curr_time = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        start_time = end_time - timedelta(hours=24)
        # Find all accounts which have done a transaction with from and to date
        inv_subquery = db.session.query(InvoiceModel.payment_account_id).filter(
            InvoiceModel.created_on < end_time).filter(InvoiceModel.created_on >= start_time).subquery()

        pad_accounts = PaymentAccountModel.query.filter(PaymentAccountModel.id.in_(inv_subquery)).all()

        for account in pad_accounts:
            # Find all PAD invoices for this account
            account_invoices = db.session.query(InvoiceModel) \
                .filter(InvoiceModel.created_on < end_time) \
                .filter(InvoiceModel.created_on >= start_time) \
                .filter(InvoiceModel.payment_account_id == account.id) \
                .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value) \
                .order_by(InvoiceModel.created_on.desc())

            # Get the first invoice id as the trx number for CFS
            transaction_number = account_invoices[0].id
            # Get cfs account
            cfs_account: CfsAccountModel = CfsAccountModel.find_active_by_account_id(account.id)

            # Create a CFS invoice
            current_app.logger.debug(f'Creating cfs invoice for {transaction_number}')
            invoice_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/invs/' \
                .format(cfs_account.cfs_party, cfs_account.cfs_account, cfs_account.cfs_site)

            # Add all lines together
            lines = []
            for invoice in account_invoices:
                lines.append(invoice.payment_line_items)

            invoice_payload = dict(
                batch_source=CFS_BATCH_SOURCE,
                cust_trx_type=CFS_CUST_TRX_TYPE,
                transaction_date=curr_time,
                transaction_number=transaction_number,
                gl_date=curr_time,
                term_name=CFS_TERM_NAME,
                comments='',
                lines=cls._build_lines(lines)
            )

            access_token = CFSService.get_token().json().get('access_token')
            invoice_response = CFSService.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                               invoice_payload)
            # Create payment records
            pad_service = PadService()
            payment = Payment.create(payment_method=pad_service.get_payment_method_code(),
                                     payment_system=pad_service.get_payment_system_code(),
                                     payment_status=pad_service.get_default_payment_status(),
                                     invoice_number=invoice_response.json().get('invoice_number'))

            # Create a transaction record
            transaction: PaymentTransactionModel = PaymentTransactionModel()
            transaction.payment_id = payment.id
            transaction.client_system_url = None
            transaction.status_code = TransactionStatus.CREATED.value
            transaction.save()

            # Iterate invoice and create invoice reference records
            for invoice in account_invoices:
                # Create invoice reference, payment record and a payment transaction
                InvoiceReference.create(
                    invoice_id=invoice.id,
                    invoice_number=invoice_response.json().get('invoice_number'),
                    reference_number=invoice_response.json().get('pbc_ref_number', None))

                # Misc
                invoice.cfs_account_id = cfs_account.id
                invoice.invoice_status_code = 'IN_PROGRESS'  # TODO set a proper status ??
                invoice.save()

    @classmethod
    def _create_online_banking_invoices(cls):
        """Create online banking invoices to CFS system."""
        curr_time = current_local_time().strftime('%Y-%m-%dT%H:%M:%SZ')
        # TODO to avoid race condition, may be fetch invoices created 30 minutes earlier ?
        online_banking_invoices = InvoiceModel.query \
            .filter_by(payment_method_code=PaymentMethod.ONLINE_BANKING.value) \
            .filter_by(invoice_status_code=InvoiceStatus.CREATED.value)

        current_app.logger.info(f'Found {len(online_banking_invoices)} to be created in CFS.')
        for invoice in online_banking_invoices:
            # Get cfs account
            cfs_account: CfsAccountModel = CfsAccountModel.find_active_by_account_id(invoice.payment_account_id)

            # Create a CFS invoice
            current_app.logger.debug(f'Creating cfs invoice for invoice {invoice.id}')
            invoice_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/invs/' \
                .format(cfs_account.cfs_party, cfs_account.cfs_account, cfs_account.cfs_site)

            invoice_payload = dict(
                batch_source=CFS_BATCH_SOURCE,
                cust_trx_type=CFS_CUST_TRX_TYPE,
                transaction_date=curr_time,
                transaction_number=invoice.id,
                gl_date=curr_time,
                term_name=CFS_TERM_NAME,
                comments='',
                lines=cls._build_lines(invoice.payment_line_items)
            )

            access_token = CFSService.get_token().json().get('access_token')
            invoice_response = CFSService.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                               invoice_payload)

            # Create invoice reference, payment record and a payment transaction
            invoice_reference: InvoiceReference = InvoiceReference.create(
                invoice_id=invoice.id,
                invoice_number=invoice_response.json().get('invoice_number'),
                reference_number=invoice_response.json().get('pbc_ref_number', None))
            online_banking_service = OnlineBankingService()
            payment = Payment.create(payment_method=online_banking_service.get_payment_method_code(),
                                     payment_system=online_banking_service.get_payment_system_code(),
                                     payment_status=online_banking_service.get_default_payment_status(),
                                     invoice_number=invoice_reference.invoice_number)

            transaction: PaymentTransactionModel = PaymentTransactionModel()
            transaction.payment_id = payment.id
            transaction.client_system_url = None
            transaction.status_code = TransactionStatus.CREATED.value
            transaction.save()

            # Misc
            invoice.cfs_account_id = cfs_account.id
            invoice.invoice_status_code = 'IN_PROGRESS'  # TODO set a proper status ??
            invoice.save()

    @classmethod
    def _build_lines(cls, payment_line_items: [PaymentLineItemModel]):
        """Build lines for the invoice."""
        lines = []
        index: int = 0
        for line_item in payment_line_items:
            # TODO populate remove memo line and populate distribution details
            index = index + 1
            lines.append(
                {
                    'line_number': index,
                    'line_type': CFS_LINE_TYPE,
                    'memo_line_name': line_item.fee_distribution.memo_name,
                    'description': line_item.description,
                    'attribute1': line_item.description,
                    'unit_price': line_item.total,
                    'quantity': 1
                }
            )
            if line_item.service_fees > 0:
                index = index + 1
                lines.append(
                    {
                        'line_number': index,
                        'line_type': CFS_LINE_TYPE,
                        'memo_line_name': line_item.fee_distribution.service_fee_memo_name,
                        'description': 'Service Fee',
                        'attribute1': 'Service Fee',
                        'unit_price': line_item.service_fees,
                        'quantity': 1
                    }
                )

        return lines
