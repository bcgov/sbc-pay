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
"""This module is being invoked from a job and it cleans up the stale records."""
import datetime

from flask import current_app
from pay_api.exceptions import BusinessException, Error
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import db
from pay_api.services import PaymentService, TransactionService
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.utils.enums import InvoiceReferenceStatus, PaymentStatus, TransactionStatus


STATUS_PAID = ('PAID', 'CMPLT')


class StalePaymentTask:  # pylint: disable=too-few-public-methods
    """Task to sync stale payments."""

    @classmethod
    def update_stale_payments(cls):
        """Update stale payments."""
        current_app.logger.info(f'StalePaymentTask Ran at {datetime.datetime.now(tz=datetime.timezone.utc)}')
        cls._update_stale_payments()
        cls._delete_marked_payments()
        cls._verify_created_direct_pay_invoices()

    @classmethod
    def _update_stale_payments(cls):
        """Update stale payment records.

        This is to handle edge cases where the user has completed payment and some error occured and payment status
        is not up-to-date.
        """
        stale_transactions = PaymentTransactionModel.find_stale_records(minutes=30)
        # Find all payments which were failed due to service unavailable error.
        service_unavailable_transactions = db.session.query(PaymentTransactionModel)\
            .join(PaymentModel, PaymentModel.id == PaymentTransactionModel.payment_id) \
            .filter(PaymentModel.payment_status_code == PaymentStatus.CREATED.value)\
            .filter(PaymentTransactionModel.pay_system_reason_code == Error.SERVICE_UNAVAILABLE.name)\
            .all()

        if len(stale_transactions) == 0 and len(service_unavailable_transactions) == 0:
            current_app.logger.info(f'Stale Transaction Job Ran at {datetime.datetime.now(tz=datetime.timezone.utc)}.'
                                    'But No records found!')
        for transaction in [*stale_transactions, *service_unavailable_transactions]:
            try:
                current_app.logger.info(f'Stale Transaction Job found records.Payment Id: {transaction.payment_id}, '
                                        f'Transaction Id : {transaction.id}')
                TransactionService.update_transaction(transaction.id, pay_response_url=None)
                current_app.logger.info(f'Stale Transaction Job Updated records.Payment Id: {transaction.payment_id}, '
                                        f'Transaction Id : {transaction.id}')
            except BusinessException as err:  # just catch and continue .Don't stop
                # If the error is for COMPLETED PAYMENT, then mark the transaction as CANCELLED
                # as there would be COMPLETED transaction in place and continue.
                if err.code == Error.COMPLETED_PAYMENT.name:
                    current_app.logger.info('Completed payment, marking transaction as CANCELLED.')
                    transaction.status_code = TransactionStatus.CANCELLED.value
                    transaction.save()
                else:
                    current_app.logger.info('Stale Transaction Error on update_transaction')
                    current_app.logger.info(err)

    @classmethod
    def _delete_marked_payments(cls):
        """Update stale payment records.

        This is to handle edge cases where the user has completed payment and some error
        occured and payment status is not up-to-date.
        """
        invoices_to_delete = InvoiceModel.find_invoices_marked_for_delete()
        if len(invoices_to_delete) == 0:
            current_app.logger.info(f'Delete Invoice Job Ran at {datetime.datetime.now(tz=datetime.timezone.utc)}.'
                                    'But No records found!')
        for invoice in invoices_to_delete:
            try:
                current_app.logger.info(f'Delete Payment Job found records.Payment Id: {invoice.id}')
                PaymentService.delete_invoice(invoice.id)
                current_app.logger.info(f'Delete Payment Job Updated records.Payment Id: {invoice.id}')
            except BusinessException as err:  # just catch and continue .Don't stop
                current_app.logger.warn('Error on delete_payment')
                current_app.logger.warn(err)

    @classmethod
    def _verify_created_direct_pay_invoices(cls):
        """Verify recent invoice with PAYBC."""
        created_invoices = InvoiceModel.find_created_direct_pay_invoices(days=2)
        current_app.logger.info(f'Found {len(created_invoices)} Created Invoices to be Verified.')

        for invoice in created_invoices:
            current_app.logger.info(f'Verify Invoice Job found records.Invoice Id: {invoice.id}')
            paybc_invoice = DirectPayService.query_order_status(invoice, InvoiceReferenceStatus.ACTIVE.value)

            if paybc_invoice.paymentstatus in STATUS_PAID:
                current_app.logger.debug('_update_active_transactions')
                transaction = TransactionService.find_active_by_invoice_id(invoice.id)
                if transaction:
                    # check existing payment status in PayBC and save receipt
                    TransactionService.update_transaction(transaction.id, pay_response_url=None)
