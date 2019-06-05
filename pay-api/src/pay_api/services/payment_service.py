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

from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.utils.enums import Status

from .base_payment_system import PaymentSystemService
from .fee_schedule import FeeSchedule
from .invoice import Invoice
from .payment import Payment
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class PaymentService:  # pylint: disable=too-few-public-methods
    """Service to manage Payment related operations."""

    @classmethod
    def create_payment(cls, payment_request: Tuple[Dict[str, Any]],  # pylint: disable=too-many-locals
                       current_user: str = None):
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
        payment_info = payment_request.get('payment_info')
        business_info = payment_request.get('business_info')
        contact_info = business_info.get('contact_info')
        filing_info = payment_request.get('filing_info')

        current_app.logger.debug('Creating PaymentSystemService impl')
        pay_service: PaymentSystemService = PaymentSystemFactory.create(payment_info.get('method_of_payment', None),
                                                                        business_info.get('corp_type', None))

        current_app.logger.debug('Calculate the fees')
        # Calculate the fees
        fees = []
        for filing_type_info in filing_info.get('filing_types'):
            current_app.logger.debug('Getting fees for {} '.format(filing_type_info.get('filing_type_code')))
            fee: FeeSchedule = FeeSchedule.find_by_corp_type_and_filing_type(
                corp_type=business_info.get('corp_type', None),
                filing_type_code=filing_type_info.get('filing_type_code', None),
                valid_date=filing_info.get('date', None),
                jurisdiction=None,
                priority=filing_info.get('priority', None))
            if filing_type_info.get('filing_description'):
                fee.description = filing_type_info.get('filing_description')

            fees.append(fee)

        current_app.logger.debug('Check if payment account exists')
        payment_account: PaymentAccount = PaymentAccount.find_account(business_info.get('business_identifier', None),
                                                                      business_info.get('corp_type', None),
                                                                      pay_service.get_payment_system_code())
        if not payment_account.id:
            current_app.logger.debug('No payment account, creating new')
            party_number, account_number, site_number = pay_service.create_account(business_info.get('business_name'),
                                                                                   contact_info)
            payment_account = PaymentAccount.create(business_info, (account_number, party_number, site_number),
                                                    pay_service.get_payment_system_code())

        current_app.logger.debug('Creating payment record for account : {}'.format(payment_account.id))

        payment: Payment = None
        pay_system_invoice: Dict[str, any] = None

        try:
            payment: Payment = Payment.create(payment_info, current_user, pay_service.get_payment_system_code())
            current_app.logger.debug(payment)

            current_app.logger.debug('Creating Invoice record for payment {}'.format(payment.id))
            invoice = Invoice.create(payment_account, payment, fees, current_user)

            line_items = []
            for fee in fees:
                current_app.logger.debug('Creating line items')
                line_items.append(PaymentLineItem.create(invoice.id, fee))
            current_app.logger.debug('Handing off to payment system to create invoice')
            pay_system_invoice = pay_service.create_invoice(payment_account, line_items, invoice.id)
            current_app.logger.debug('Updating invoice record')
            invoice = Invoice.find_by_id(invoice.id)
            invoice.invoice_status_code = Status.CREATED.value
            invoice.reference_number = pay_system_invoice.get('reference_number', None)
            invoice.invoice_number = pay_system_invoice.get('invoice_number', None)
            invoice.save()
            payment.commit()
        except Exception as e:
            current_app.logger.error('Rolling back as error occured!')
            current_app.logger.error(e)
            if payment:
                payment.rollback()
            if pay_system_invoice:
                pay_service.cancel_invoice(
                    (payment_account.party_number, payment_account.account_number, payment_account.site_number),
                    pay_system_invoice.get('invoice_number'))
            raise

        current_app.logger.debug('>create_payment')

        return payment.asdict()

    def get_payment(cls, payment_id):
        payment: Payment = None
        try:
            payment: Payment = Payment.find_by_id(payment_id)
            return payment
        except Exception as e:
            raise e


