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
from requests import HTTPError

from pay_api.exceptions import BusinessException, Error
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import db
from pay_api.services import InvoiceService, PaymentService, TransactionService
from pay_api.services.direct_sale_service import DirectSaleService
from pay_api.utils.enums import InvoiceReferenceStatus, PaymentMethod, PaymentStatus, TransactionStatus

STATUS_PAID = ("PAID", "CMPLT")


class StalePaymentTask:  # pylint: disable=too-few-public-methods
    """Task to sync stale payments."""

    @classmethod
    def update_stale_payments(cls, daily_run=False):
        """Update stale payments."""
        current_app.logger.info(f"StalePaymentTask Ran at {datetime.datetime.now(tz=datetime.UTC)}")
        cls._update_stale_payments()
        cls._delete_marked_payments()
        cls._verify_created_credit_card_invoices(daily_run)

    @classmethod
    def _update_stale_payments(cls):
        """Update stale payment records.

        This is to handle edge cases where the user has completed payment and some error occured and payment status
        is not up-to-date. This handles short term scenarios.
        """
        # Note stale transactions can cover the NSF case, but this is only 30 minutes.
        stale_transactions = PaymentTransactionModel.find_stale_records(minutes=30)
        # Find all payments which were failed due to service unavailable error.
        service_unavailable_transactions = (
            db.session.query(PaymentTransactionModel)
            .join(PaymentModel, PaymentModel.id == PaymentTransactionModel.payment_id)
            .filter(PaymentModel.payment_status_code == PaymentStatus.CREATED.value)
            .filter(PaymentTransactionModel.pay_system_reason_code == Error.SERVICE_UNAVAILABLE.name)
            .all()
        )

        if len(stale_transactions) == 0 and len(service_unavailable_transactions) == 0:
            current_app.logger.info(f"Ran at {datetime.datetime.now(tz=datetime.UTC)}.But No records found!")
        for transaction in [*stale_transactions, *service_unavailable_transactions]:
            try:
                current_app.logger.info(
                    f"Found records.Payment Id: {transaction.payment_id}, Transaction Id : {transaction.id}"
                )
                TransactionService.update_transaction(transaction.id, pay_response_url=None)
                current_app.logger.info(
                    f"Updated records.Payment Id: {transaction.payment_id}, Transaction Id : {transaction.id}"
                )
            except BusinessException as err:  # just catch and continue .Don't stop
                # If the error is for COMPLETED PAYMENT, then mark the transaction as CANCELLED
                # as there would be COMPLETED transaction in place and continue.
                if err.code == Error.COMPLETED_PAYMENT.name:
                    current_app.logger.info("Completed payment, marking transaction as CANCELLED.")
                    transaction.status_code = TransactionStatus.CANCELLED.value
                    transaction.save()
                else:
                    current_app.logger.info("Stale Transaction Error on update_transaction")
                    current_app.logger.info(err)

    @classmethod
    def _delete_marked_payments(cls):
        """Update stale payment records.

        This is to handle edge cases where the user has completed payment and some error
        occured and payment status is not up-to-date.
        """
        invoices_to_delete = InvoiceModel.find_invoices_marked_for_delete()
        if len(invoices_to_delete) == 0:
            current_app.logger.info(
                f"Delete Invoice Job Ran at {datetime.datetime.now(tz=datetime.UTC)}.But No records found!"
            )
        for invoice in invoices_to_delete:
            try:
                current_app.logger.info(f"Delete Payment Job found records.Payment Id: {invoice.id}")
                PaymentService.delete_invoice(invoice.id)
                current_app.logger.info(f"Delete Payment Job Updated records.Payment Id: {invoice.id}")
            except BusinessException as err:  # just catch and continue .Don't stop
                current_app.logger.warn("Error on delete_payment")
                current_app.logger.warn(err)

    @classmethod
    def _verify_created_credit_card_invoices(cls, daily_run):
        """Verify recent invoice with PAYBC."""
        days = 30 if daily_run else 2
        invoices = InvoiceService.find_created_invoices(payment_method=PaymentMethod.DIRECT_PAY.value, days=days)
        if daily_run:
            invoices += InvoiceService.find_created_invoices(payment_method=PaymentMethod.CC.value, days=90)
        current_app.logger.info(f"Found {len(invoices)} created invoices to be verified.")
        for invoice in invoices:
            current_app.logger.info(f"Verifying invoice: {invoice.id}")
            cls._handle_direct_sale_invoice(invoice)
            cls._handle_direct_pay_invoice(invoice)

    @classmethod
    def _handle_direct_pay_invoice(cls, invoice: InvoiceModel):
        """Handle NSF or shopping cart credit card invoices.

        This handles the longer scenario up to 90 days.
        """
        # DIRECT_PAY are actually DirectSale invoices.
        if invoice.payment_method_code == PaymentMethod.DIRECT_PAY.value:
            return
        try:
            # Note: CREATED is handled by find_stale_records, might not need in job, doesn't handle FAILED though.
            if not (
                transaction := TransactionService.should_process_transaction(
                    invoice.id, [TransactionStatus.FAILED.value, TransactionStatus.CREATED.value]
                )
            ):
                return
            TransactionService.update_transaction(transaction.id, pay_response_url=None)
        except Exception as err:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(f"Error verifying invoice {invoice.id}: {err}", exc_info=True)

    @classmethod
    def _handle_direct_sale_invoice(cls, invoice: InvoiceModel):
        """Handle regular direct sale invoices, these are 99% of transactions."""
        # CC invoices are true DirectPay invoices.
        if invoice.payment_method_code == PaymentMethod.CC.value:
            return
        try:
            paybc_invoice = DirectSaleService.query_order_status(invoice, InvoiceReferenceStatus.ACTIVE.value)
            if paybc_invoice.paymentstatus not in STATUS_PAID:
                return
            if not (
                transaction := TransactionService.should_process_transaction(
                    invoice.id, [TransactionStatus.CREATED.value, TransactionStatus.FAILED.value]
                )
            ):
                return
            # check existing payment status in PayBC and save receipt
            TransactionService.update_transaction(transaction.id, pay_response_url=None)
        except HTTPError as http_err:
            if http_err.response is None or http_err.response.status_code != 404:
                current_app.logger.error(
                    f"HTTPError on verifying invoice {invoice.id}: {http_err}",
                    exc_info=True,
                )
            current_app.logger.info(f"Invoice not found (404) at PAYBC. Skipping invoice id: {invoice.id}")
        except Exception as err:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(f"Error verifying invoice {invoice.id}: {err}", exc_info=True)
