# Copyright © 2024 Province of British Columbia
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
"""Service to manage Fee Calculation."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, List

import humps
from flask import current_app
from sentry_sdk import capture_message
from sbc_common_components.utils.dataclasses import PaymentToken
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import PaymentTransactionSchema
from pay_api.services import gcp_queue_publisher
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.services.receipt import Receipt
from pay_api.utils.enums import (
    InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, QueueSources, TransactionStatus)
from pay_api.utils.errors import Error
from pay_api.utils.util import get_topic_for_corp_type, is_valid_redirect_url

from .payment import Payment


class PaymentTransaction:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment transaction operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: uuid = None
        self._status_code: str = None
        self._payment_id: int = None
        self._client_system_url: str = None
        self._pay_system_url: str = None
        self._transaction_start_time: datetime = None
        self._transaction_end_time: datetime = None
        self._pay_system_reason_code: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentTransactionModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: uuid = self._dao.id
        self.status_code: str = self._dao.status_code
        self.payment_id: int = self._dao.payment_id
        self.client_system_url: str = self._dao.client_system_url
        self.pay_system_url: str = self._dao.pay_system_url
        self.transaction_start_time: datetime = self._dao.transaction_start_time
        self.transaction_end_time: datetime = self._dao.transaction_end_time
        self.pay_system_reason_code: str = self._dao.pay_system_reason_code

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: uuid):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def status_code(self):
        """Return the status_code."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str):
        """Set the status_code."""
        self._status_code = value
        self._dao.status_code = value

    @property
    def payment_id(self):
        """Return the payment_id."""
        return self._payment_id

    @payment_id.setter
    def payment_id(self, value: int):
        """Set the corp_type_code."""
        self._payment_id = value
        self._dao.payment_id = value

    @property
    def client_system_url(self):
        """Return the client_system_url."""
        return self._client_system_url

    @client_system_url.setter
    def client_system_url(self, value: str):
        """Set the client_system_url."""
        self._client_system_url = value
        self._dao.client_system_url = value

    @property
    def pay_system_url(self):
        """Return the pay_system_url."""
        return self._pay_system_url

    @pay_system_url.setter
    def pay_system_url(self, value: str):
        """Set the account_number."""
        self._pay_system_url = value
        self._dao.pay_system_url = value

    @property
    def transaction_start_time(self):
        """Return the transaction_start_time."""
        return self._transaction_start_time

    @transaction_start_time.setter
    def transaction_start_time(self, value: datetime):
        """Set the transaction_start_time."""
        self._transaction_start_time = value
        self._dao.transaction_start_time = value

    @property
    def transaction_end_time(self):
        """Return the transaction_end_time."""
        return self._transaction_end_time

    @transaction_end_time.setter
    def transaction_end_time(self, value: datetime):
        """Set the transaction_end_time."""
        self._transaction_end_time = value
        self._dao.transaction_end_time = value

    @property
    def pay_system_reason_code(self):
        """Return the pay_system_reason_code."""
        return self._pay_system_reason_code

    @pay_system_reason_code.setter
    def pay_system_reason_code(self, value: str):
        """Set the pay_system_reason_code."""
        self._pay_system_reason_code = value
        self._dao.pay_system_reason_code = value

    def asdict(self):
        """Return the invoice as a python dict."""
        txn_schema = PaymentTransactionSchema()
        d = txn_schema.dump(self._dao)

        return d

    @staticmethod
    def populate(value):
        """Populate the service."""
        if not value:
            return None
        return PaymentTransaction.__wrap_dao(value)

    def save(self):
        """Save the fee schedule information."""
        return self._dao.save()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    @staticmethod
    def create_transaction_for_payment(payment_id: int, request_json: Dict) -> PaymentTransaction:
        """Create transaction record for payment."""
        payment: Payment = Payment.find_by_id(payment_id)
        if not payment.id or payment.payment_status_code != PaymentStatus.CREATED.value:
            raise BusinessException(Error.INVALID_PAYMENT_ID)

        # Check if return url is valid
        PaymentTransaction._validate_redirect_url_and_throw_error(
            payment.payment_method_code, request_json.get('clientSystemUrl')
        )

        transaction = PaymentTransaction._create_transaction(payment, request_json)
        return transaction

    @staticmethod
    def create_transaction_for_invoice(invoice_id: int, request_json: Dict) -> PaymentTransaction:
        """Create transaction record for invoice, by creating a payment record if doesn't exist."""
        # Lookup invoice record
        invoice: Invoice = Invoice.find_by_id(invoice_id, skip_auth_check=True)
        if not invoice.id:
            raise BusinessException(Error.INVALID_INVOICE_ID)
        current_app.logger.info(f'Creating a transaction record for invoice {invoice_id}, '
                                f'{invoice.payment_method_code}, {invoice.invoice_status_code}')
        if invoice.payment_method_code == PaymentMethod.PAD.value:  # No transaction needed for PAD invoices.
            raise BusinessException(Error.INVALID_TRANSACTION)

        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
            payment_method=invoice.payment_method_code
        )
        current_app.logger.debug(f'Created Pay System instance : {pay_system_service}')
        # Check if return url is valid
        PaymentTransaction._validate_redirect_url_and_throw_error(
            invoice.payment_method_code, request_json.get('clientSystemUrl')
        )

        # Check if there is a payment created. If not, create a payment record with status CREATED
        payment = Payment.find_payment_for_invoice(invoice_id)
        if not payment:
            # Transaction is against payment, so create a payment if not present.
            invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)

            # Create a payment record
            payment = Payment.create(payment_method=pay_system_service.get_payment_method_code(),
                                     payment_system=pay_system_service.get_payment_system_code(),
                                     payment_status=pay_system_service.get_default_payment_status(),
                                     invoice_number=invoice_reference.invoice_number,
                                     invoice_amount=invoice.total,
                                     payment_account_id=invoice.payment_account_id)

        transaction = PaymentTransaction._create_transaction(payment, request_json, invoice=invoice)
        current_app.logger.debug('>create transaction')

        return transaction

    @staticmethod
    def _create_transaction(payment: Payment, request_json: Dict, invoice: Invoice = None):
        # Cannot start transaction on completed payment
        current_app.logger.info(f'Creating transactional record {payment.invoice_number}, '
                                f'{payment.payment_status_code}')
        if payment.payment_status_code in (PaymentStatus.COMPLETED.value, PaymentStatus.DELETED.value):
            raise BusinessException(Error.COMPLETED_PAYMENT)

        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
            # todo Remove this and use payment.payment_method_code when payment methods are not created upfront
            payment_method=invoice.payment_method_code if invoice else payment.payment_method_code
        )

        # If there are active transactions (status=CREATED), then invalidate all of them and create a new one.
        existing_transaction = PaymentTransactionModel.find_active_by_payment_id(payment.id)
        if existing_transaction and existing_transaction.status_code != TransactionStatus.CANCELLED.value:
            current_app.logger.info('Found existing transaction. Setting as CANCELLED.')
            existing_transaction.status_code = TransactionStatus.CANCELLED.value
            existing_transaction.transaction_end_time = datetime.now(tz=timezone.utc)
            existing_transaction.save()
        transaction = PaymentTransaction()
        transaction.payment_id = payment.id
        transaction.client_system_url = request_json.get('clientSystemUrl')
        transaction.status_code = TransactionStatus.CREATED.value
        transaction_dao = transaction.flush()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        if invoice:
            transaction.pay_system_url = PaymentTransaction._build_pay_system_url_for_invoice(
                invoice, pay_system_service, transaction.id, request_json.get('payReturnUrl')
            )
        else:
            transaction.pay_system_url = PaymentTransaction._build_pay_system_url_for_payment(
                payment, pay_system_service, transaction.id, request_json.get('payReturnUrl')
            )
        transaction_dao = transaction.save()
        transaction = PaymentTransaction.__wrap_dao(transaction_dao)
        return transaction

    @staticmethod
    def _validate_redirect_url_and_throw_error(payment_method: str, return_url: str):
        """Check and Throw if the return_url is not a valid url."""
        is_validity_check_needed = payment_method in (
            PaymentMethod.CC.value, PaymentMethod.DIRECT_PAY.value)
        if is_validity_check_needed and not is_valid_redirect_url(return_url):
            raise BusinessException(Error.INVALID_REDIRECT_URI)

    @staticmethod
    def _build_pay_system_url_for_invoice(invoice: Invoice, pay_system_service: PaymentSystemService,
                                          transaction_id: uuid, pay_return_url: str):
        """Build pay system url which will be used to redirect to the payment system."""
        current_app.logger.debug('<build_pay_system_url')
        invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
        return_url = f'{pay_return_url}/{invoice.id}/transaction/{transaction_id}'

        current_app.logger.debug('>build_pay_system_url')
        return pay_system_service.get_payment_system_url_for_invoice(invoice, invoice_reference, return_url)

    @staticmethod
    def _build_pay_system_url_for_payment(payment: Payment, pay_system_service: PaymentSystemService,
                                          transaction_id: uuid, pay_return_url: str):
        """Build pay system url which will be used to redirect to the payment system."""
        current_app.logger.debug('<build_pay_system_url')
        invoice_reference = InvoiceReference.find_any_active_reference_by_invoice_number(payment.invoice_number)
        return_url = f'{pay_return_url}/{payment.id}/transaction/{transaction_id}'

        current_app.logger.debug('>build_pay_system_url')
        return pay_system_service.get_payment_system_url_for_payment(payment, invoice_reference, return_url)

    @staticmethod
    def find_by_id(transaction_id: uuid):
        """Find transaction by id."""
        current_app.logger.debug(f'>find_by_id {transaction_id}')
        transaction_dao = PaymentTransactionModel.find_by_id(transaction_id)
        if not transaction_dao:
            raise BusinessException(Error.INVALID_TRANSACTION_ID)

        transaction = PaymentTransaction.__wrap_dao(transaction_dao)

        current_app.logger.debug('>find_by_id')
        return transaction

    @staticmethod
    def find_active_by_invoice_id(invoice_id: int):
        """Find active transaction by invoice id."""
        current_app.logger.debug('>find_active_by_invoice_id')
        active_transaction = PaymentTransactionModel.find_active_by_invoice_id(invoice_id)
        return PaymentTransaction.populate(active_transaction)

    @staticmethod
    def update_transaction(transaction_id: uuid,  # pylint: disable=too-many-locals
                           pay_response_url: str):
        """Update transaction record.

        Does the following:
        1. Find the payment record with the id
        2. Find the invoice record using the payment identifier
        3. Call the pay system service and get the receipt details
        4. Save the receipt record
        5. Change the status of Invoice
        6. Change the status of Payment
        7. Update the transaction record
        """
        #  TODO for now assumption is this def will be called only for credit card, bcol and internal payments.
        #  When start to look into the PAD and Online Banking may need to refactor here
        transaction_dao: PaymentTransactionModel = PaymentTransactionModel.find_by_id(
            transaction_id
        )
        if not transaction_dao:
            raise BusinessException(Error.INVALID_TRANSACTION_ID)
        if transaction_dao.status_code == TransactionStatus.COMPLETED.value:
            raise BusinessException(Error.INVALID_TRANSACTION)
        current_app.logger.info(f'Updating transaction record for {transaction_id}, {transaction_dao.status_code}')
        payment: Payment = Payment.find_by_id(transaction_dao.payment_id)
        payment_account: PaymentAccount = PaymentAccount.find_by_id(payment.payment_account_id)
        current_app.logger.info(f'Updating transaction for {payment.invoice_number} ({payment.payment_status_code}), '
                                f'Account {payment_account.auth_account_id}')

        # For transactions other than Credit Card, there could be more than one invoice per payment.
        invoices: List[Invoice] = Invoice.find_invoices_for_payment(transaction_dao.payment_id)

        if payment.payment_status_code == PaymentStatus.COMPLETED.value:
            current_app.logger.info('Stale payment found.')
            # if the transaction status is EVENT_FAILED then publish to queue and return, else raise error
            if transaction_dao.status_code == TransactionStatus.EVENT_FAILED.value:
                transaction_dao.status_code = TransactionStatus.COMPLETED.value

                # Publish status to Queue
                for invoice in invoices:
                    current_app.logger.info(f'Publishing stale payment for Invoice {invoice.id}.')
                    PaymentTransaction.publish_status(transaction_dao, invoice)

                return PaymentTransaction.__wrap_dao(transaction_dao.save())

            raise BusinessException(Error.COMPLETED_PAYMENT)

        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
            payment_method=payment.payment_method_code
        )
        current_app.logger.info(f'Pay system instance created {pay_system_service}')
        invoice_reference = InvoiceReference.find_any_active_reference_by_invoice_number(payment.invoice_number)
        try:
            receipt_details = pay_system_service.get_receipt(payment_account, pay_response_url, invoice_reference)
            txn_reason_code = None
            transaction_dao.pay_system_reason_code = None
        except ServiceUnavailableException as exc:
            txn_reason_code = exc.status
            transaction_dao.pay_system_reason_code = txn_reason_code
            receipt_details = None
        except Exception as exc:  # noqa pylint: disable=unused-variable, broad-except
            receipt_details = None

        current_app.logger.info(f'Receipt details for {payment.invoice_number} : {receipt_details}')
        if receipt_details:
            PaymentTransaction._update_receipt_details(invoices, payment, receipt_details, transaction_dao)
        else:
            transaction_dao.status_code = TransactionStatus.FAILED.value

        # check if the pay_response_url contains any failure status
        if not txn_reason_code:
            pay_system_reason_code = pay_system_service.get_pay_system_reason_code(pay_response_url)
            transaction_dao.pay_system_reason_code = pay_system_reason_code

        # Save response URL
        transaction_dao.transaction_end_time = datetime.now(tz=timezone.utc)
        transaction_dao.pay_response_url = pay_response_url
        transaction_dao = transaction_dao.save()

        # Publish message to unlock account if account is locked.
        if payment.payment_status_code == PaymentStatus.COMPLETED.value:
            active_failed_payments = Payment.get_failed_payments(auth_account_id=payment_account.auth_account_id)
            current_app.logger.info('active_failed_payments %s', active_failed_payments)
            # Note this will take some thought if we have multiple payment methods running at once in the future.
            if not active_failed_payments or payment_account.has_overdue_invoices:
                PaymentAccount.unlock_frozen_accounts(payment_id=payment.id,
                                                      payment_account_id=payment.payment_account_id,
                                                      invoice_number=payment.invoice_number)

        transaction = PaymentTransaction.__wrap_dao(transaction_dao)

        current_app.logger.debug('>update_transaction')
        return transaction

    @staticmethod
    def _update_receipt_details(invoices, payment, receipt_details, transaction_dao):
        """Update receipt details to invoice."""
        payment.paid_amount = receipt_details[2]
        payment.payment_date = datetime.now(tz=timezone.utc)
        transaction_dao.status_code = TransactionStatus.COMPLETED.value

        if float(payment.paid_amount) < float(payment.invoice_amount):
            current_app.logger.critical('ALERT : Paid Amount is less than owed amount.  Paid : %s, Owed- %s',
                                        payment.paid_amount, payment.invoice_amount)
            capture_message(f'ALERT : Paid Amount is less than owed amount.  Paid : {payment.paid_amount}, '
                            f'Owed: {payment.invoice_amount}', level='error')
        else:
            payment.receipt_number = receipt_details[0]
            payment.payment_status_code = PaymentStatus.COMPLETED.value

            for invoice in invoices:
                # Save receipt details for each invoice
                PaymentTransaction.__save_receipt(invoice, receipt_details)
                invoice.paid = invoice.total  # set the paid amount as total
                invoice.invoice_status_code = InvoiceStatus.PAID.value
                invoice.payment_date = datetime.now(tz=timezone.utc)
                invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
                invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
                # TODO If it's not PAD, publish message. Refactor and move to pay system service later.
                if invoice.payment_method_code != PaymentMethod.PAD.value:
                    current_app.logger.info(f'Release record for invoice : {invoice.id} ')
                    PaymentTransaction.publish_status(transaction_dao, invoice)

    @staticmethod
    def __wrap_dao(transaction_dao):
        transaction = PaymentTransaction()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        return transaction

    @staticmethod
    def __save_receipt(invoice, receipt_details):
        receipt: Receipt = Receipt.find_by_invoice_id_and_receipt_number(invoice.id, receipt_details[0])
        if not receipt.id:
            receipt: Receipt = Receipt()
            receipt.receipt_number = receipt_details[0]
            receipt.receipt_date = receipt_details[1]
            receipt.receipt_amount = receipt_details[2]
            receipt.invoice_id = invoice.id
        else:
            receipt.receipt_date = receipt_details[1]
            receipt.receipt_amount = receipt_details[2]

        # Save receipt details to DB.
        receipt.flush()
        return receipt

    @staticmethod
    def find_by_invoice_id(invoice_id: int):
        """Find all transactions by invoice id."""
        transactions_dao = PaymentTransactionModel.find_by_invoice_id(invoice_id)
        data: Dict = {'items': []}
        if transactions_dao:
            for transaction_dao in transactions_dao:
                data['items'].append(PaymentTransaction.populate(transaction_dao).asdict())

        current_app.logger.debug('>find_by_payment_id')
        return data

    @staticmethod
    def publish_status(transaction_dao: PaymentTransactionModel, invoice: Invoice):
        """Publish payment/transaction status to the Queue."""
        current_app.logger.debug('<publish_status')
        if transaction_dao.status_code == TransactionStatus.COMPLETED.value:
            if invoice.invoice_status_code == InvoiceStatus.PAID.value:
                status_code = TransactionStatus.COMPLETED.value
            else:
                current_app.logger.info(f'Status {invoice.invoice_status_code} received for invoice {invoice.id}')
                return
        else:
            status_code = 'TRANSACTION_FAILED'

        try:
            gcp_queue_publisher.publish_to_queue(
                QueueMessage(
                    source=QueueSources.PAY_API.value,
                    message_type=QueueMessageTypes.PAYMENT.value,
                    payload=PaymentTransaction.create_event_payload(invoice, status_code),
                    topic=get_topic_for_corp_type(invoice.corp_type_code)
                )
            )

        except Exception as e:  # NOQA pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.warning(
                f'Notification to Queue failed, marking the transaction : {transaction_dao.id} as EVENT_FAILED',
                e)
            transaction_dao.status_code = TransactionStatus.EVENT_FAILED.value
        current_app.logger.debug('>publish_status')

    @staticmethod
    def create_event_payload(invoice, status_code):
        """Create event payload for payment events."""
        return humps.camelize(asdict(PaymentToken(invoice.id, status_code, invoice.filing_id, invoice.corp_type_code)))
