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
from pay_api.exceptions import BusinessException
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.services import PaymentService, TransactionService


class StalePaymentTask:  # pylint: disable=too-few-public-methods
    """Task to sync stale payments."""

    @classmethod
    def update_stale_payments(cls):
        """Update stale payments."""
        current_app.logger.info(f'StalePaymentTask Ran at {datetime.datetime.now()}')
        cls._update_stale_payments()
        cls._delete_marked_payments()

    @classmethod
    def _update_stale_payments(cls):
        """Update stale payment records.

        This is to handle edge cases where the user has completed payment and some error occured and payment status
        is not up-to-date.
        """
        stale_transactions = PaymentTransactionModel.find_stale_records(minutes=30)
        if len(stale_transactions) == 0:
            current_app.logger.info(f'Stale Transaction Job Ran at {datetime.datetime.now()}.But No records found!')
        for transaction in stale_transactions:
            try:
                current_app.logger.info(
                    'Stale Transaction Job found records.Payment Id: {}, Transaction Id : {}'.format(
                        transaction.payment_id,
                        transaction.id))
                TransactionService.update_transaction(transaction.id, '')
                current_app.logger.info(
                    'Stale Transaction Job Updated records.Payment Id: {}, Transaction Id : {}'.format(
                        transaction.payment_id, transaction.id))
            except BusinessException as err:  # just catch and continue .Don't stop
                current_app.logger.error('Stale Transaction Error on update_transaction')
                current_app.logger.error(err)

    @classmethod
    def _delete_marked_payments(cls):
        """Update stale payment records.

        This is to handle edge cases where the user has completed payment and some error
        occured and payment status is not up-to-date.
        """
        invoices_to_delete = InvoiceModel.find_invoices_marked_for_delete()
        if len(invoices_to_delete) == 0:
            current_app.logger.info(f'Delete Invoice Job Ran at {datetime.datetime.now()}.But No records found!')
        for invoice in invoices_to_delete:
            try:
                current_app.logger.info('Delete Payment Job found records.Payment Id: {}'.format(invoice.id))
                PaymentService.delete_invoice(invoice.id)
                current_app.logger.info(
                    'Delete Payment Job Updated records.Payment Id: {}'.format(invoice.id))
            except BusinessException as err:  # just catch and continue .Don't stop
                current_app.logger.error('Error on delete_payment')
                current_app.logger.error(err)
