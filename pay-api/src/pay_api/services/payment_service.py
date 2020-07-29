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

from threading import Thread
from typing import Any, Dict, Tuple

from flask import copy_current_request_context, current_app

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.enums import PaymentSystem, PaymentStatus, InvoiceStatus, LineItemStatus, InvoiceReferenceStatus
from pay_api.utils.errors import Error
from pay_api.utils.util import get_str_by_path

from .base_payment_system import PaymentSystemService
from .fee_schedule import FeeSchedule
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .payment import Payment
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem
from .payment_transaction import PaymentTransaction


class PaymentService:  # pylint: disable=too-few-public-methods
    """Service to manage Payment related operations."""

    @classmethod
    def create_payment(cls, payment_request: Tuple[Dict[str, Any]], authorization: Tuple[Dict[str, Any]]):
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
        current_app.logger.debug('<create_payment')
        business_info = payment_request.get('businessInfo')
        contact_info = business_info.get('contactInfo')
        filing_info = payment_request.get('filingInfo')
        account_info = payment_request.get('accountInfo', None)
        filing_id = filing_info.get('filingIdentifier', None)
        folio_number = filing_info.get('folioNumber', get_str_by_path(authorization, 'business/folioNumber'))

        corp_type = business_info.get('corpType', None)
        payment_method = _get_payment_method(payment_request, authorization)

        # Calculate the fees
        current_app.logger.debug('Calculate the fees')
        fees = _calculate_fees(corp_type, filing_info)

        # Create payment system instance from factory
        current_app.logger.debug('Creating PaymentSystemService impl')
        pay_service: PaymentSystemService = PaymentSystemFactory.create(
            payment_method=payment_method,
            corp_type=corp_type,
            fees=sum(fee.total for fee in fees),
            account_info=account_info
        )

        # Create payment account
        payment_account = _create_account(pay_service, business_info, contact_info, account_info, authorization)

        payment: Payment = None
        pay_system_invoice: Dict[str, any] = None

        try:
            payment: Payment = Payment.create(pay_service.get_payment_method_code(),
                                              pay_service.get_payment_system_code())

            current_app.logger.debug('Creating Invoice record for payment {}'.format(payment.id))
            invoice = Invoice.create(payment_account, payment.id, fees, corp_type,
                                     routing_slip=get_str_by_path(account_info, 'routingSlip'),
                                     dat_number=get_str_by_path(account_info, 'datNumber'),
                                     filing_id=filing_id, folio_number=folio_number,
                                     business_identifier=business_info.get('businessIdentifier'))

            line_items = []
            for fee in fees:
                current_app.logger.debug('Creating line items')
                line_items.append(PaymentLineItem.create(invoice.id, fee))
            current_app.logger.debug('Handing off to payment system to create invoice')
            # DONE
            pay_system_invoice = pay_service.create_invoice(payment_account, line_items, invoice,
                                                            corp_type_code=invoice.corp_type_code)

            current_app.logger.debug('Updating invoice record')
            invoice = Invoice.find_by_id(invoice.id, skip_auth_check=True)
            invoice.invoice_status_code = InvoiceStatus.CREATED.value
            invoice.save()
            InvoiceReference.create(invoice.id, pay_system_invoice.get('invoice_number', None),
                                    pay_system_invoice.get('reference_number', None))

            payment.commit()
            _complete_post_payment(pay_service, payment)
            payment = Payment.find_by_id(payment.id, skip_auth_check=True)

        except Exception as e:
            current_app.logger.error('Rolling back as error occured!')
            current_app.logger.error(e)
            if payment:
                payment.rollback()
            if pay_system_invoice:
                pay_service.cancel_invoice(
                    payment_account,
                    pay_system_invoice.get('invoice_number'),
                )
            raise

        current_app.logger.debug('>create_payment')

        return payment.asdict()

    @classmethod
    def get_payment(cls, payment_id):
        """Get payment related records."""
        try:
            payment: Payment = Payment.find_by_id(payment_id)
            if not payment.id:
                raise BusinessException(Error.INVALID_PAYMENT_ID)

            return payment.asdict()
        except Exception as e:
            current_app.logger.debug('Error on get payment {}', e)
            raise

    @classmethod
    def update_payment(cls, payment_id: int, payment_request: Tuple[Dict[str, Any]],
                       authorization: Tuple[Dict[str, Any]]):
        # pylint: disable=too-many-locals,too-many-statements
        """Update payment related records.

        Does the following;
        1. Calculate the fees based on the filing types received.
        2. Check if the payment account exists,
            3.1 If yes, use the one from database.
            3.2 Else create one in payment system and update database.
        3. Check PayBC invoice status
            1.1 If payment completed, do not update the payment,
            1.2 Else continue the process.
        4. Get invoice record in database.
        5. Invalidate old payment line items and create new payment line items in database and flush.
        6. Update invoice in payment system;
            6.1 If successful update the invoice table with references from payment system.
                6.1.1 If failed adjust the invoice to zero and roll back the transaction.
            6.2 If fails rollback the transaction
        7. Update payment record in database and flush.
        """
        current_app.logger.debug('<update_payment')
        business_info = payment_request.get('businessInfo')
        filing_info = payment_request.get('filingInfo')

        corp_type = business_info.get('corpType', None)
        payment_method = _get_payment_method(payment_request, authorization)

        current_app.logger.debug('Calculate the fees')
        # Calculate the fees
        fees = _calculate_fees(business_info.get('corpType'), filing_info)

        current_app.logger.debug('Creating PaymentSystemService impl')

        pay_service: PaymentSystemService = PaymentSystemFactory.create(
            payment_method=payment_method,
            corp_type=corp_type,
            fees=sum(fee.total for fee in fees)
        )

        current_app.logger.debug('Check if payment account exists')

        payment: Payment = None

        try:
            # update transaction function will update the status from PayBC
            _update_active_transactions(payment_id)

            payment: Payment = Payment.find_by_id(payment_id, skip_auth_check=True)
            _check_if_payment_is_completed(payment)

            current_app.logger.debug('Updating Invoice record for payment {}'.format(payment.id))
            invoices = payment.invoices
            for invoice in invoices:
                if invoice.invoice_status_code == InvoiceStatus.CREATED.value:
                    payment_line_items = invoice.payment_line_items

                    # Invalidate active payment line items
                    for payment_line_item in payment_line_items:
                        if payment_line_item.line_item_status_code != LineItemStatus.CANCELLED.value:
                            payment_line_item.line_item_status_code = LineItemStatus.CANCELLED.value
                            payment_line_item.save()

                    # add new payment line item(s)
                    line_items = []
                    for fee in fees:
                        current_app.logger.debug('Creating line items')
                        line_items.append(PaymentLineItem.create(invoice.id, fee))
                    current_app.logger.debug('Handing off to payment system to update invoice')

                    # Mark the current active invoice reference as CANCELLED
                    inv_number: str = None
                    for reference in invoice.references:
                        if reference.status_code == InvoiceReferenceStatus.ACTIVE.value:
                            inv_number = reference.invoice_number
                            reference.status_code = InvoiceReferenceStatus.CANCELLED.value
                            reference.flush()

                    # update invoice
                    payment_account: PaymentAccount = PaymentAccount.find_by_pay_system_id(
                        credit_account_id=invoice.credit_account_id,
                        internal_account_id=invoice.internal_account_id,
                        bcol_account_id=invoice.bcol_account_id)

                    pay_system_invoice = pay_service.update_invoice(
                        payment_account,
                        line_items,
                        invoice.id,
                        inv_number,
                        len(invoice.references),
                        corp_type_code=invoice.corp_type_code
                    )
                    current_app.logger.debug('Updating invoice record')
                    invoice = Invoice.find_by_id(invoice.id, skip_auth_check=True)
                    invoice.total = sum(fee.total for fee in fees)
                    invoice.save()

                    InvoiceReference.create(invoice.id, pay_system_invoice.get('invoice_number', None),
                                            pay_system_invoice.get('reference_number', None))

            payment.save()
            payment.commit()
            _complete_post_payment(pay_service, payment)
            # return payment with updated contents
            payment = Payment.find_by_id(payment.id, skip_auth_check=True)
        except Exception as e:
            current_app.logger.error('Rolling back as error occurred!')
            current_app.logger.error(e)
            if payment:
                payment.rollback()
            raise

        current_app.logger.debug('>update_payment')

        return payment.asdict()

    @classmethod
    def delete_payment(cls, payment_id: int):  # pylint: disable=too-many-locals,too-many-statements
        """Delete payment related records.

        Does the following;
        1. Check if payment is eligible to be deleted.
        2. Mark the payment and invoices records as deleted.
        3. Publish message to queue
        """
        current_app.logger.debug('<delete_payment')

        # update transaction function will update the status from PayBC
        _update_active_transactions(payment_id)

        payment: Payment = Payment.find_by_id(payment_id, skip_auth_check=True)
        _check_if_payment_is_completed(payment)

        # Create the payment system implementation
        pay_service: PaymentSystemService = PaymentSystemFactory.create_from_system_code(
            payment.payment_system_code, payment.payment_method_code)

        # Cancel all invoices
        for invoice in payment.invoices:
            invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
            payment_account = PaymentAccount.find_by_pay_system_id(
                credit_account_id=invoice.credit_account_id,
                internal_account_id=invoice.internal_account_id,
                bcol_account_id=invoice.bcol_account_id)
            pay_service.cancel_invoice(payment_account=payment_account,
                                       inv_number=invoice_reference.invoice_number)
            invoice.invoice_status_code = InvoiceStatus.DELETED.value
            for line in invoice.payment_line_items:
                line.line_item_status_code = LineItemStatus.CANCELLED.value
            invoice.save()
            invoice_reference.status_code = InvoiceReferenceStatus.CANCELLED.value
            invoice_reference.save()

        payment.payment_status_code = PaymentStatus.DELETED.value
        payment.save()

        current_app.logger.debug('>delete_payment')

    @classmethod
    def accept_delete(cls, payment_id: int):  # pylint: disable=too-many-locals,too-many-statements
        """Mark payment related records to be deleted."""
        current_app.logger.debug('<accept_delete')
        payment: Payment = Payment.find_by_id(payment_id, one_of_roles=[EDIT_ROLE])
        _check_if_payment_is_completed(payment)
        payment.payment_status_code = PaymentStatus.DELETE_ACCEPTED.value
        payment.save()

        @copy_current_request_context
        def run_delete():
            """Call delete payment."""
            PaymentService.delete_payment(payment_id)

        current_app.logger.debug('Starting thread to delete payment.')
        thread = Thread(target=run_delete)
        thread.start()
        current_app.logger.debug('>delete_payment')


def _calculate_fees(corp_type, filing_info):
    """Calculate and return the fees based on the filing type codes."""
    fees = []
    for filing_type_info in filing_info.get('filingTypes'):
        current_app.logger.debug('Getting fees for {} '.format(filing_type_info.get('filingTypeCode')))
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
        if filing_type_info.get('filingDescription'):
            fee.description = filing_type_info.get('filingDescription')

        fees.append(fee)
    return fees


def _create_account(pay_service, business_info, contact_info, account_info, authorization):
    """Create account in pay system and save it in pay db."""
    current_app.logger.debug('Check if payment account exists')
    payment_account: PaymentAccount = PaymentAccount.find_account(
        business_info,
        authorization,
        pay_service.get_payment_system_code(),
        pay_service.get_payment_method_code(),
    )
    if not payment_account.id:
        current_app.logger.debug('No payment account, creating new')
        name = business_info.get('businessName', get_str_by_path(authorization, 'account/name'))
        pay_system_account = pay_service.create_account(
            name=name,
            contact_info=contact_info,
            account_info=account_info,
            authorization=authorization
        )

        current_app.logger.debug('Creating payment record for account : {}'.format(payment_account.id))
        payment_account = PaymentAccount.create(
            business_info=business_info,
            account_details=pay_system_account,
            payment_system=pay_service.get_payment_system_code(),
            payment_method=pay_service.get_payment_method_code(),
            authorization=authorization
        )
    return payment_account


def _complete_post_payment(pay_service: PaymentSystemService, payment: Payment):
    """Complete the post payment actions.

    For internal payments, create and complete the transactions and receipt.
    """
    if pay_service.get_payment_system_code() in (PaymentSystem.INTERNAL.value, PaymentSystem.BCOL.value):
        transaction: PaymentTransaction = PaymentTransaction.create(payment.id,
                                                                    {
                                                                        'clientSystemUrl': '',
                                                                        'payReturnUrl': ''
                                                                    })
        transaction.update_transaction(payment.id, transaction.id, receipt_number=None)


def _update_active_transactions(payment_id):
    # get existing payment transaction
    current_app.logger.debug('<_update_active_transactions')
    transaction: PaymentTransaction = PaymentTransaction.find_active_by_payment_id(payment_id)
    if transaction:
        # check existing payment status in PayBC;
        PaymentTransaction.update_transaction(payment_id, transaction.id, None)


def _check_if_payment_is_completed(payment):
    if payment.payment_status_code in (PaymentStatus.COMPLETED.value, PaymentStatus.DELETED.value):
        raise BusinessException(Error.COMPLETED_PAYMENT)


def _get_payment_method(payment_request: Dict, authorization: Dict):
    payment_method = get_str_by_path(payment_request, 'paymentInfo/methodOfPayment')
    if not payment_method:
        payment_method = get_str_by_path(authorization, 'account/paymentPreference/methodOfPayment')
    if not payment_method:
        payment_method = 'CC'
    return payment_method
