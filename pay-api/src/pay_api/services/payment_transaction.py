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
"""Service to manage Fee Calculation."""

import uuid
from datetime import datetime
from typing import Dict

from flask import current_app

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import PaymentTransactionSchema
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.services.receipt import Receipt
from pay_api.utils.enums import PaymentSystem, PaymentStatus, TransactionStatus, InvoiceReferenceStatus, InvoiceStatus
from pay_api.utils.errors import Error
from pay_api.utils.util import is_valid_redirect_url
from .invoice import InvoiceModel
from .payment import Payment
from .queue_publisher import publish_response


class PaymentTransaction:  # pylint: disable=too-many-instance-attributes
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
        """Set the payment_id."""
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

    def asdict(self):
        """Return the invoice as a python dict."""
        txn_schema = PaymentTransactionSchema()
        d = txn_schema.dump(self._dao)
        if self.pay_system_reason_code:
            d['pay_system_reason_code'] = self.pay_system_reason_code

        return d

    @staticmethod
    def populate(value):
        """Pouplate the service."""
        if not value:
            return None
        transaction: PaymentTransaction = PaymentTransaction()
        transaction._dao = value  # pylint: disable=protected-access
        return transaction

    def save(self):
        """Save the fee schedule information."""
        return self._dao.save()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    @staticmethod
    def create(payment_identifier: str, request_json: Dict):
        """Create transaction record."""
        current_app.logger.debug('<create transaction')
        # Lookup payment record
        payment: Payment = Payment.find_by_id(payment_identifier, skip_auth_check=True)

        # Check if return url is valid
        return_url = request_json.get('clientSystemUrl')
        if payment.payment_system_code == PaymentSystem.PAYBC.value and not is_valid_redirect_url(return_url):
            raise BusinessException(Error.INVALID_REDIRECT_URI)

        if not payment.id:
            raise BusinessException(Error.INVALID_PAYMENT_ID)
        # Cannot start transaction on completed payment
        if payment.payment_status_code in (PaymentStatus.COMPLETED.value,
                                           PaymentStatus.DELETED.value, PaymentStatus.DELETE_ACCEPTED.value):
            raise BusinessException(Error.COMPLETED_PAYMENT)

        # If there are active transactions (status=CREATED), then invalidate all of them and create a new one.
        existing_transactions = PaymentTransactionModel.find_by_payment_id(payment.id)
        if existing_transactions:
            for existing_transaction in existing_transactions:
                if existing_transaction.status_code != TransactionStatus.CANCELLED.value:
                    existing_transaction.status_code = TransactionStatus.CANCELLED.value
                    existing_transaction.transaction_end_time = datetime.now()
                    existing_transaction.save()

        transaction = PaymentTransaction()
        transaction.payment_id = payment.id
        transaction.client_system_url = return_url
        transaction.status_code = TransactionStatus.CREATED.value
        transaction_dao = transaction.flush()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        transaction.pay_system_url = transaction.build_pay_system_url(payment, transaction.id,
                                                                      request_json.get('payReturnUrl'))
        transaction_dao = transaction.save()

        transaction = PaymentTransaction()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        current_app.logger.debug('>create transaction')

        return transaction

    @staticmethod
    def build_pay_system_url(payment: Payment, transaction_id: uuid, pay_return_url: str):
        """Build pay system url which will be used to redirect to the payment system."""
        current_app.logger.debug('<build_pay_system_url')
        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_system_code(
            payment_system=payment.payment_system_code,
            payment_method=payment.payment_method_code
        )
        invoice = InvoiceModel.find_by_payment_id(payment.id)
        invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
        return_url = f'{pay_return_url}/{payment.id}/transaction/{transaction_id}'

        current_app.logger.debug('>build_pay_system_url')
        return pay_system_service.get_payment_system_url(Invoice.populate(invoice), invoice_reference, return_url)

    @staticmethod
    def find_by_id(payment_identifier: int, transaction_id: uuid):
        """Find transaction by id."""
        transaction_dao = PaymentTransactionModel.find_by_id_and_payment_id(transaction_id, payment_identifier)
        if not transaction_dao:
            raise BusinessException(Error.INVALID_TRANSACTION_ID)

        transaction = PaymentTransaction()
        transaction._dao = transaction_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return transaction

    @staticmethod
    def find_active_by_payment_id(payment_identifier: int):
        """Find active transaction by id."""
        current_app.logger.debug('>find_active_by_payment_id')
        active_transaction = PaymentTransactionModel.find_active_by_payment_id(payment_identifier)
        return PaymentTransaction.populate(active_transaction)

    @staticmethod
    def update_transaction(payment_identifier: int, transaction_id: uuid,  # pylint: disable=too-many-locals
                           receipt_number: str):
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
        transaction_dao: PaymentTransactionModel = PaymentTransactionModel.find_by_id_and_payment_id(
            transaction_id, payment_identifier
        )
        if not transaction_dao:
            raise BusinessException(Error.INVALID_TRANSACTION_ID)
        if transaction_dao.status_code == TransactionStatus.COMPLETED.value:
            raise BusinessException(Error.INVALID_TRANSACTION)

        payment: Payment = Payment.find_by_id(payment_identifier, skip_auth_check=True)

        if payment.payment_status_code == PaymentStatus.COMPLETED.value:
            raise BusinessException(Error.COMPLETED_PAYMENT)

        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_system_code(
            payment_system=payment.payment_system_code,
            payment_method=payment.payment_method_code
        )

        invoice = Invoice.find_by_payment_identifier(payment_identifier, skip_auth_check=True)
        invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
        payment_account = PaymentAccount.find_by_pay_system_id(
            credit_account_id=invoice.credit_account_id,
            internal_account_id=invoice.internal_account_id,
            bcol_account_id=invoice.bcol_account_id)

        try:
            receipt_details = pay_system_service.get_receipt(payment_account, receipt_number, invoice_reference)
            txn_reason_code = None
        except ServiceUnavailableException as exc:
            txn_reason_code = exc.status
            receipt_details = None

        if receipt_details:
            # Find if a receipt exists with same receipt_number for the invoice
            receipt = PaymentTransaction.__save_receipt(invoice, receipt_details)

            invoice.paid = receipt.receipt_amount

            if invoice.paid == invoice.total:
                invoice.invoice_status_code = InvoiceStatus.PAID.value
                payment.payment_status_code = PaymentStatus.COMPLETED.value
                payment.save()

                invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
                invoice_reference.save()

            invoice.save()

            transaction_dao.status_code = TransactionStatus.COMPLETED.value
        else:
            transaction_dao.status_code = TransactionStatus.FAILED.value

        transaction_dao.transaction_end_time = datetime.now()

        # Publish status to Queue
        PaymentTransaction.publish_status(transaction_dao, payment, invoice.filing_id)

        transaction_dao = transaction_dao.save()

        transaction = PaymentTransaction()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        transaction.pay_system_reason_code = txn_reason_code

        current_app.logger.debug('>update_transaction')
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
        receipt.save()
        return receipt

    @staticmethod
    def find_by_payment_id(payment_identifier: int):
        """Find all transactions by payment id."""
        transactions_dao = PaymentTransactionModel.find_by_payment_id(payment_identifier)
        data: Dict = {'items': []}
        if transactions_dao:
            for transaction_dao in transactions_dao:
                data['items'].append(PaymentTransaction.populate(transaction_dao).asdict())

        current_app.logger.debug('>find_by_payment_id')
        return data

    @staticmethod
    def publish_status(transaction_dao: PaymentTransactionModel, payment: Payment, filing_id: str = None):
        """Publish payment/transaction status to the Queue."""
        current_app.logger.debug('<publish_status')
        if transaction_dao.status_code == TransactionStatus.COMPLETED.value:
            if payment.payment_status_code == PaymentStatus.COMPLETED.value:
                status_code = TransactionStatus.COMPLETED.value
            else:
                current_app.logger.info(f'Status {payment.payment_status_code} received for payment {payment.id}')
                return
        else:
            status_code = 'TRANSACTION_FAILED'

        payload = {
            'paymentToken': {
                'id': payment.id,
                'statusCode': status_code,
                'filingIdentifier': filing_id
            }
        }

        try:
            publish_response(payload=payload)
        except Exception as e:  # pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.warning(
                f'Notification to Queue failed, marking the transaction : {transaction_dao.id} as EVENT_FAILED',
                e)
            transaction_dao.status_code = TransactionStatus.EVENT_FAILED.value
        current_app.logger.debug('>publish_status')
