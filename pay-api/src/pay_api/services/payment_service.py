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
"""Service to manage Payment."""

from datetime import date

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.utils.errors import Error
from typing import Any, Dict, Tuple
from pay_api.services.paybc_service import PaybcService
from .payment import Payment
from .invoice import Invoice

from .fee_schedule import FeeSchedule
from .payment_system_factory import PaymentSystemFactory
from .base_payment_system import PaymentSystemService
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class PaymentService:
    """Service to manage Payment related operations."""

    @classmethod
    def create_payment(cls, payment_request: Tuple[Dict[str, Any]]):
        """Create payment related records."""
        current_app.logger.debug('<create_payment')

        payment_info = payment_request.get('payment_info')
        business_info = payment_request.get('business_info')
        contact_info = payment_request.get('contact_info')
        filing_info = payment_request.get('filing_info')

        # TODO DI Pay BC
        pay_service: PaymentSystemService = PaymentSystemFactory.create(payment_info.get('method_of_payment', None),
                                                                        business_info.get('corp_type', None))

        # Calculate the fees
        fees = []
        for filing_type_info in filing_info.get('filing_types'):
            fee: FeeSchedule = FeeSchedule.find_by_corp_type_and_filing_type(
                corp_type=business_info.get('corp_type', None),
                filing_type_code=filing_type_info.get('filing_type_code', None),
                valid_date=filing_info.get('date', None),
                jurisdiction=None,
                priority=filing_info.get('priority', None))
            if not filing_type_info.get('filing_description'):
                fee.description = filing_type_info.get('filing_description')

            fees.append(fee.asdict())

        """
        Step 1 : Check if payment account exists in DB, 
                If yes : Check if the account is valid in payment system.
                If no  : Create account in payment system and update the DB, 
        Step 2 : 
            Create Payment record - flush
            Create Invoice record - flush
            Create line items - flush
        Step 3 :
            Create invoice in payment system:
                If success : Update the invoice table with reference and invoice numbers, commit transaction:
                    If fails adjust the invoice to zero in payment system else Return with payment identfier
                If failed  : rollback the transaction (except account creation)
        """
        payment_account = PaymentAccount.find_account(business_info.get('business_identifier', None),
                                                      business_info.get('corp_type', None),
                                                      pay_service.get_payment_system_code())
        if payment_account:
            payment_account_dict = payment_account.asdict()
            if not pay_service.is_valid_account(payment_account_dict.get('party_number'),
                                                payment_account_dict.get('account_number'),
                                                payment_account_dict.get('site_number')):
                payment_account.delete()
                payment_account = None
        if not payment_account:
            party_number, account_number, site_number = pay_service.create_account(business_info.get('business_name'),
                                                                                   contact_info)
            payment_account = PaymentAccount.create(business_info, account_number, party_number, site_number)

        payment = Payment.create(payment_info, fees, pay_service.get_payment_system_code())

        invoice = Invoice.create(payment_account, payment, fees)
        line_items: [PaymentLineItem] = []
        for fee in fees:
            line_items.append(PaymentLineItem.create(invoice.id, fee))

        pay_system_invoice = pay_service.create_invoice(payment_account, line_items, invoice.id)

        invoice = Invoice.find_by_id(invoice.id)
        invoice.invoice_status_code = 'CREATE'
        invoice.reference_number = pay_system_invoice.get('pbc_ref_number', None)
        invoice.invoice_number = pay_system_invoice.get('invoice_number', None)

        invoice.save()

        current_app.logger.debug('>create_payment')

        return None
