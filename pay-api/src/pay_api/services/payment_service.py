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
from datetime import datetime
from typing import Any, Dict, Tuple

from flask import current_app
from flask_jwt_oidc import JwtManager

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.enums import PaymentSystem, Status
from pay_api.utils.errors import Error

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
    def create_payment(cls, payment_request: Tuple[Dict[str, Any]], token_info: Dict):
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
        current_user = token_info.get('preferred_username', None)
        payment_info = payment_request.get('paymentInfo')
        business_info = payment_request.get('businessInfo')
        contact_info = business_info.get('contactInfo')
        filing_info = payment_request.get('filingInfo')
        account_info = payment_request.get('accountInfo', None)
        routing_slip_number = account_info.get('routingSlip', None) if account_info else None
        filing_id = filing_info.get('filingIdentifier', None)

        corp_type = business_info.get('corpType', None)
        payment_method = payment_info.get('methodOfPayment', None)

        current_app.logger.debug('Calculate the fees')
        # Calculate the fees
        fees = _calculate_fees(corp_type, filing_info)

        current_app.logger.debug('Creating PaymentSystemService impl')
        pay_service: PaymentSystemService = PaymentSystemFactory.create(
            token_info,
            payment_method=payment_method,
            corp_type=corp_type,
            fees=sum(fee.total for fee in fees)
        )

        payment_account = _create_account(pay_service, business_info, contact_info)

        payment: Payment = None
        pay_system_invoice: Dict[str, any] = None

        try:
            payment: Payment = Payment.create(payment_info, current_user, pay_service.get_payment_system_code())
            current_app.logger.debug(payment)

            current_app.logger.debug('Creating Invoice record for payment {}'.format(payment.id))
            invoice = Invoice.create(payment_account, payment.id, fees, current_user, routing_slip=routing_slip_number,
                                     filing_id=filing_id)

            line_items = []
            for fee in fees:
                current_app.logger.debug('Creating line items')
                line_items.append(PaymentLineItem.create(invoice.id, fee))
            current_app.logger.debug('Handing off to payment system to create invoice')
            pay_system_invoice = pay_service.create_invoice(payment_account, line_items, invoice.id)
            current_app.logger.debug('Updating invoice record')
            invoice = Invoice.find_by_id(invoice.id, skip_auth_check=True)
            invoice.invoice_status_code = Status.CREATED.value
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
                    (payment_account.party_number, payment_account.account_number, payment_account.site_number),
                    pay_system_invoice.get('invoice_number'),
                )
            raise

        current_app.logger.debug('>create_payment')

        return payment.asdict()

    @classmethod
    def get_payment(cls, payment_id, jwt):
        """Get payment related records."""
        try:
            payment: Payment = Payment.find_by_id(payment_id, jwt=jwt)
            if not payment.id:
                raise BusinessException(Error.PAY005)

            return payment.asdict()
        except Exception as e:
            current_app.logger.debug('Error on get payment {}', e)
            raise

    @classmethod
    def update_payment(cls, payment_id: int, payment_request: Tuple[Dict[str, Any]], token_info: Dict):
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
        current_user = token_info.get('preferred_username', None)
        payment_info = payment_request.get('paymentInfo')
        business_info = payment_request.get('businessInfo')
        filing_info = payment_request.get('filingInfo')

        corp_type = business_info.get('corpType', None)
        payment_method = payment_info.get('methodOfPayment', None)

        current_app.logger.debug('Calculate the fees')
        # Calculate the fees
        fees = _calculate_fees(business_info.get('corpType'), filing_info)

        current_app.logger.debug('Creating PaymentSystemService impl')

        pay_service: PaymentSystemService = PaymentSystemFactory.create(
            token_info,
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
                if invoice.invoice_status_code in (Status.DRAFT.value, Status.CREATED.value, Status.PARTIAL.value):
                    payment_line_items = invoice.payment_line_items

                    # Invalidate active payment line items
                    for payment_line_item in payment_line_items:
                        if payment_line_item.line_item_status_code != Status.DELETED.value:
                            payment_line_item.line_item_status_code = Status.DELETED.value
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
                        if reference.status_code == Status.CREATED.value:
                            inv_number = reference.invoice_number
                            reference.status_code = Status.CANCELLED.value
                            reference.flush()

                    # update invoice
                    payment_account: PaymentAccount = PaymentAccount.find_by_id(invoice.account_id)

                    pay_system_invoice = pay_service.update_invoice(
                        payment_account,
                        line_items,
                        invoice.id,
                        inv_number,
                        len(invoice.references)
                    )
                    current_app.logger.debug('Updating invoice record')
                    invoice = Invoice.find_by_id(invoice.id, skip_auth_check=True)
                    invoice.updated_on = datetime.now()
                    invoice.updated_by = current_user
                    invoice.total = sum(fee.total for fee in fees)
                    invoice.save()

                    InvoiceReference.create(invoice.id, pay_system_invoice.get('invoice_number', None),
                                            pay_system_invoice.get('reference_number', None))

            payment.updated_on = datetime.now()
            payment.updated_by = current_user
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
    def delete_payment(cls, payment_id: int, jwt: JwtManager,
                       token_info: Dict):  # pylint: disable=too-many-locals,too-many-statements
        """Delete payment related records.

        Does the following;
        1. Check if payment is eligible to be deleted.
        2. Mark the payment and invoices records as deleted.
        3. Publish message to queue
        """

        current_app.logger.debug('<delete_payment')

        # update transaction function will update the status from PayBC
        _update_active_transactions(payment_id)

        payment: Payment = Payment.find_by_id(payment_id, jwt=jwt, one_of_roles=[EDIT_ROLE])
        _check_if_payment_is_completed(payment)

        # Create the payment system implementation
        pay_service: PaymentSystemService = PaymentSystemFactory.create_from_system_code(payment.payment_system_code)

        # Cancel all invoices
        for invoice in payment.invoices:
            invoice_reference = InvoiceReference.find_active_reference_by_invoice_id(invoice.id)
            pay_service.cancel_invoice(account_details=(invoice.account.party_number,
                                                        invoice.account.account_number,
                                                        invoice.account.site_number),
                                       inv_number=invoice_reference.invoice_number)
            invoice.updated_by = token_info.get('username')
            invoice.updated_on = datetime.now()
            invoice.invoice_status_code = Status.DELETED.value
            for line in invoice.payment_line_items:
                line.line_item_status_code = Status.DELETED.value
            invoice.save()
            invoice_reference.status_code = Status.DELETED.value
            invoice_reference.save()

        payment.updated_by = token_info.get('username')
        payment.updated_on = datetime.now()
        payment.payment_status_code = Status.DELETED.value
        payment.save()

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
            priority=filing_info.get('priority', None),
        )
        if filing_type_info.get('filingDescription'):
            fee.description = filing_type_info.get('filingDescription')

        fees.append(fee)
    return fees


def _create_account(pay_service, business_info, contact_info):
    """Create account in pay system and save it in pay db."""
    current_app.logger.debug('Check if payment account exists')
    payment_account: PaymentAccount = PaymentAccount.find_account(
        business_info.get('businessIdentifier'),
        business_info.get('corpType'),
        pay_service.get_payment_system_code(),
    )
    if not payment_account.id:
        current_app.logger.debug('No payment account, creating new')
        pay_system_account = pay_service.create_account(
            business_info.get('businessName'), contact_info
        )

        current_app.logger.debug('Creating payment record for account : {}'.format(payment_account.id))
        payment_account = PaymentAccount.create(
            business_info, pay_system_account, pay_service.get_payment_system_code()
        )
    return payment_account


def _complete_post_payment(pay_service: PaymentSystemService, payment: Payment):
    """Complete the post payment actions.

    For internal payments, create and complete the transactions and receipt.
    """
    if pay_service.get_payment_system_code() == PaymentSystem.INTERNAL.value:
        transaction: PaymentTransaction = PaymentTransaction.create(payment.id,
                                                                    {
                                                                        'clientSystemUrl': '',
                                                                        'payReturnUrl': ''
                                                                    },
                                                                    skip_auth_check=True)
        transaction.update_transaction(payment.id, transaction.id, receipt_number=None, skip_auth_check=True)


def _update_active_transactions(payment_id):
    # get existing payment transaction
    transaction: PaymentTransaction = PaymentTransaction.find_active_by_payment_id(payment_id)
    current_app.logger.debug(transaction)
    if transaction:
        # check existing payment status in PayBC;
        PaymentTransaction.update_transaction(payment_id, transaction.id, None, skip_auth_check=True)


def _check_if_payment_is_completed(payment):
    if payment.payment_status_code in (Status.COMPLETED.value, Status.DELETED.value):
        raise BusinessException(Error.PAY010)
