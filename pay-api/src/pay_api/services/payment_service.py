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
"""Service class to control all the operations related to Payment."""
from decimal import Decimal
from threading import Thread
from typing import Any, Dict, Tuple

from flask import copy_current_request_context, current_app

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus
from pay_api.utils.errors import Error
from pay_api.utils.util import get_str_by_path

from .base_payment_system import PaymentSystemService
from .fee_schedule import FeeSchedule
from .flags import flags
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .payment import Payment
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem
from .payment_transaction import PaymentTransaction


class PaymentService:  # pylint: disable=too-few-public-methods
    """Service to manage Payment related operations."""

    @classmethod
    def create_invoice(cls, payment_request: Tuple[Dict[str, Any]], authorization: Tuple[Dict[str, Any]]) -> Dict:
        # pylint: disable=too-many-locals, too-many-statements
        """Create payment related records.

        Does the following;
        1. Calculate the fees based on the filing types received.
        2. Check if the payment account exists,
            2.1 If yes, use the one from database.
            2.2 Else create one in payment system and update database.
        3. Create payment record in database and flush.
        4. Create invoice record in database and flush.
        5. Create payment line items in database and flush.
        6. Create invoice in payment system;
            6.1 If successful update the invoice table with references from payment system.
                6.1.1 If failed adjust the invoice to zero and roll back the transaction.
            6.2 If fails rollback the transaction
        """
        business_info = payment_request.get('businessInfo')
        filing_info = payment_request.get('filingInfo')
        account_info = payment_request.get('accountInfo', None)
        corp_type = business_info.get('corpType', None)
        business_identifier = business_info.get('businessIdentifier')

        payment_account = cls._find_payment_account(authorization)
        payment_method = _get_payment_method(payment_request, payment_account)

        if payment_method == PaymentMethod.EFT.value and not flags.is_on('enable-eft-payment-method', default=False):
            raise BusinessException(Error.INVALID_PAYMENT_METHOD)

        current_app.logger.info(f'Creating Payment Request : '
                                f'{payment_method}, {corp_type}, {business_identifier}, '
                                f'{payment_account.auth_account_id}')

        bcol_account = cls._get_bcol_account(account_info, payment_account)

        # Calculate the fees
        fees = _calculate_fees(corp_type, filing_info)

        # Create payment system instance from factory
        pay_service: PaymentSystemService = PaymentSystemFactory.create(
            payment_method=payment_method,
            corp_type=corp_type,
            fees=sum(fee.total for fee in fees),
            account_info=account_info,
            payment_account=payment_account
        )
        current_app.logger.info(f'Created Pay System Instance : {pay_service}')

        pay_system_invoice: Dict[str, any] = None
        invoice: Invoice = None

        try:
            invoice = Invoice()
            invoice.bcol_account = bcol_account
            invoice.payment_account_id = payment_account.id
            invoice.cfs_account_id = payment_account.cfs_account_id
            invoice.invoice_status_code = pay_service.get_default_invoice_status()
            invoice.service_fees = sum(fee.service_fees for fee in fees) if fees else 0
            invoice.total = sum(fee.total for fee in fees) if fees else 0
            invoice.paid = 0
            invoice.refund = 0
            invoice.routing_slip = get_str_by_path(account_info, 'routingSlip')
            invoice.filing_id = filing_info.get('filingIdentifier', None)
            invoice.dat_number = get_str_by_path(account_info, 'datNumber')
            invoice.folio_number = filing_info.get('folioNumber', None)
            invoice.business_identifier = business_identifier
            invoice.payment_method_code = pay_service.get_payment_method_code()
            invoice.corp_type_code = corp_type
            details = payment_request.get('details')
            if not details or details == 'null':
                details = []
            invoice.details = details
            invoice = invoice.flush()

            line_items = []
            for fee in fees:
                line_items.append(PaymentLineItem.create(invoice.id, fee))

            current_app.logger.info(f'Handing off to payment system to create invoice for {invoice.id}')
            invoice_reference = pay_service.create_invoice(payment_account, line_items, invoice,
                                                           corp_type_code=invoice.corp_type_code)

            invoice.commit()

            pay_service.complete_post_invoice(invoice, invoice_reference)

            invoice = Invoice.find_by_id(invoice.id, skip_auth_check=True)

        except Exception as e:  # NOQA pylint: disable=broad-except
            current_app.logger.error('Rolling back as error occured!')
            current_app.logger.error(e)
            if invoice:
                invoice.rollback()
            if pay_system_invoice:
                pay_service.cancel_invoice(
                    payment_account,
                    pay_system_invoice.get('invoice_number'),
                )
            raise

        current_app.logger.debug('>Finished creating payment request')

        return invoice.asdict(include_dynamic_fields=True)

    @classmethod
    def _find_payment_account(cls, authorization):
        # find payment account
        payment_account: PaymentAccount = PaymentAccount.find_account(authorization)

        # If there is no payment_account it must be a request with no account (NR, Staff payment etc.)
        # and invoked using a service account or a staff token
        if not payment_account:
            payment_method = get_str_by_path(authorization,
                                             'account/paymentInfo/methodOfPayment') or _get_default_payment()
            payment_account = PaymentAccount.create(
                {
                    'accountId': get_str_by_path(authorization, 'account/id'),
                    'paymentInfo': {
                        'methodOfPayment': payment_method
                    }
                }
            )
        return payment_account

    @classmethod
    def _get_bcol_account(cls, account_info, payment_account: PaymentAccount):
        if account_info and account_info.get('bcolAccountNumber', None):
            bcol_account = account_info.get('bcolAccountNumber')
        else:
            bcol_account = payment_account.bcol_account
        return bcol_account

    @classmethod
    def update_invoice(cls, invoice_id: int, payment_request: Tuple[Dict[str, Any]], is_apply_credit: bool = False):
        """Update invoice related records."""
        current_app.logger.debug('<update_invoice')

        invoice: Invoice = Invoice.find_by_id(invoice_id, skip_auth_check=False)
        # If the call is to apply credit, apply credit and release records.
        if is_apply_credit:
            credit_balance = Decimal('0')
            payment_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)
            invoice_balance = invoice.total - (invoice.paid or 0)
            if (payment_account.credit or 0) >= invoice_balance:
                pay_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
                    invoice.payment_method_code)
                # Only release records, as the actual status change should happen during reconciliation.
                pay_service.apply_credit(invoice)
                credit_balance = payment_account.credit - invoice_balance
                invoice.paid = invoice.total
                invoice.save()
            elif (payment_account.credit or 0) <= invoice_balance:
                invoice.paid = (invoice.paid or 0) + (payment_account.credit or 0)
                invoice.save()

            payment_account.credit = credit_balance
            payment_account.save()
        else:
            payment_method = get_str_by_path(payment_request, 'paymentInfo/methodOfPayment')

            is_not_currently_on_ob = invoice.payment_method_code != PaymentMethod.ONLINE_BANKING.value
            is_not_changing_to_cc = payment_method not in (PaymentMethod.CC.value, PaymentMethod.DIRECT_PAY.value)
            # can patch only if the current payment method is OB
            if is_not_currently_on_ob or is_not_changing_to_cc:
                raise BusinessException(Error.INVALID_REQUEST)

            # check if it has any invoice references already created
            # if there is any invoice ref , send them to the invoiced credit card flow

            invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
            if invoice_reference:
                invoice.payment_method_code = PaymentMethod.CC.value
            else:
                pay_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
                    PaymentMethod.DIRECT_PAY.value)
                payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)
                pay_service.create_invoice(payment_account, invoice.payment_line_items, invoice,
                                           corp_type_code=invoice.corp_type_code)

                invoice.payment_method_code = PaymentMethod.DIRECT_PAY.value
            invoice.save()
        current_app.logger.debug('>update_invoice')
        return invoice.asdict()

    @classmethod
    def delete_invoice(cls, invoice_id: int):  # pylint: disable=too-many-locals,too-many-statements
        """Delete invoice related records.

        Does the following;
        1. Check if payment is eligible to be deleted.
        2. Mark the payment and invoices records as deleted.
        3. Publish message to queue
        """
        # update transaction function will update the status from PayBC
        _update_active_transactions(invoice_id)

        invoice: Invoice = Invoice.find_by_id(invoice_id, skip_auth_check=True)
        current_app.logger.debug(f'<Delete Invoice {invoice_id}, {invoice.invoice_status_code}')

        # Create the payment system implementation
        pay_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(invoice.payment_method_code)

        # set payment status as deleted
        payment = Payment.find_payment_for_invoice(invoice_id)
        _check_if_invoice_can_be_deleted(invoice, payment)

        if payment:
            payment.payment_status_code = PaymentStatus.DELETED.value
            payment.flush()

        # Cancel invoice
        invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
        payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)

        if invoice_reference:
            pay_service.cancel_invoice(payment_account=payment_account, inv_number=invoice_reference.invoice_number)
        invoice.invoice_status_code = InvoiceStatus.DELETED.value

        for line in invoice.payment_line_items:
            line.line_item_status_code = LineItemStatus.CANCELLED.value

        if invoice_reference:
            invoice_reference.status_code = InvoiceReferenceStatus.CANCELLED.value
            invoice_reference.flush()

        invoice.save()

        current_app.logger.debug('>delete_invoice')

    @classmethod
    def accept_delete(cls, invoice_id: int):  # pylint: disable=too-many-locals,too-many-statements
        """Mark payment related records to be deleted."""
        current_app.logger.debug('<accept_delete')
        invoice: Invoice = Invoice.find_by_id(invoice_id, one_of_roles=[EDIT_ROLE])

        _check_if_invoice_can_be_deleted(invoice)
        invoice.payment_status_code = InvoiceStatus.DELETE_ACCEPTED.value
        invoice.save()

        @copy_current_request_context
        def run_delete():
            """Call delete payment."""
            PaymentService.delete_invoice(invoice_id)

        current_app.logger.debug('Starting thread to delete invoice.')
        thread = Thread(target=run_delete)
        thread.start()
        current_app.logger.debug('>accept_delete')


def _calculate_fees(corp_type, filing_info):
    """Calculate and return the fees based on the filing type codes."""
    fees = []
    service_fee_applied: bool = False
    for filing_type_info in filing_info.get('filingTypes'):
        current_app.logger.debug(f"Getting fees for {filing_type_info.get('filingTypeCode')} ")
        fee: FeeSchedule = FeeSchedule.find_by_corp_type_and_filing_type(
            corp_type=corp_type,
            filing_type_code=filing_type_info.get('filingTypeCode', None),
            valid_date=filing_info.get('date', None),
            jurisdiction=None,
            is_priority=filing_type_info.get('priority'),
            is_future_effective=filing_type_info.get('futureEffective'),
            waive_fees=filing_type_info.get('waiveFees'),
            quantity=filing_type_info.get('quantity')
        )
        # If service fee is already applied, do not charge again.
        if service_fee_applied:
            fee.service_fees = 0
        elif fee.service_fees > 0:
            service_fee_applied = True

        if fee.variable:
            fee.fee_amount = Decimal(str(filing_type_info.get('fee', 0)))

        if filing_type_info.get('filingDescription'):
            fee.description = filing_type_info.get('filingDescription')

        fees.append(fee)
    return fees


def _update_active_transactions(invoice_id: int):
    # update active transactions
    current_app.logger.debug('<_update_active_transactions')
    transaction: PaymentTransaction = PaymentTransaction.find_active_by_invoice_id(invoice_id)
    if transaction:
        # check existing payment status in PayBC;
        PaymentTransaction.update_transaction(transaction.id, pay_response_url=None)


def _check_if_invoice_can_be_deleted(invoice: Invoice, payment: Payment = None):
    if invoice.invoice_status_code in (InvoiceStatus.PAID.value, InvoiceStatus.DELETED.value,
                                       InvoiceStatus.APPROVED.value):
        raise BusinessException(Error.COMPLETED_PAYMENT)
    if payment and payment.payment_status_code in (PaymentStatus.COMPLETED.value, PaymentStatus.DELETED.value):
        raise BusinessException(Error.COMPLETED_PAYMENT)


def _get_payment_method(payment_request: Dict, payment_account: PaymentAccount):
    # If no methodOfPayment is provided, use the one against the payment account table.
    payment_method = get_str_by_path(payment_request, 'paymentInfo/methodOfPayment')
    if not payment_method:
        payment_method = payment_account.payment_method
    if not payment_method:
        payment_method = _get_default_payment()
    return payment_method


def _get_default_payment() -> str:
    return PaymentMethod.DIRECT_PAY.value
