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


class PaymentService:
    """Service to manage Payment related operations."""

    @classmethod
    def create_payment(cls, payment_request: Tuple[Dict[str, Any]]):
        """Create payment related records."""
        current_app.logger.debug('<create_payment')

        payment_info = payment_request.get('payment_info')
        business_info = payment_request.get('business_info')
        filing_info = payment_request.get('filing_info')

        # TODO DI Pay BC
        pay_service: PaymentSystemService = PaymentSystemFactory.create(payment_info.get('method_of_payment', None),
                                                                        business_info.get('corp_type', None))

        # Calculate the fees
        fees = []
        for filing_type_info in filing_info.get('filing_types'):
            fees.append(FeeSchedule.find_by_corp_type_and_filing_type(
                corp_type=business_info.get('corp_type', None),
                filing_type_code=filing_type_info.get('filing_type_code', None),
                valid_date=filing_info.get('date', None),
                jurisdiction=None,
                priority=filing_info.get('priority', None)).asdict())

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
        payment_account = PaymentAccount.query()??
        if payment_account:
            if not pay_service.is_valid_account():
                payment_account.delete()
                payment_account = None
        if not payment_account:
            party_number, account_number, site_number = pay_service.create_account(business_info.get('business_name'))
            PaymentAccount.create()??


        Payment.create(payment_info, fees)
        Invoice.create()??
        PaymentLineItem.create() - iter

        inv = pay_service.create_invoice()
        Invoice.update()
        commit()

        current_app.logger.debug('>create_payment')

        return None
