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
"""Service to manage Internal Payments.

There are conditions where the payment will be handled internally. For e.g, zero $ or staff payments.
"""
import decimal
from datetime import datetime
from typing import List

from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentMethod, PaymentSystem
from pay_api.utils.util import generate_transaction_number

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem
from ..exceptions import BusinessException
from ..utils.errors import Error


class InternalPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_code(self):
        """Return INTERNAL as the system code."""
        return PaymentSystem.INTERNAL.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number."""
        current_app.logger.debug('<create_invoice')
        if routing_slip_number := invoice.routing_slip:
            routing_slip = RoutingSlipModel.find_by_number(routing_slip_number)
            if routing_slip:
                if routing_slip.remaining_amount < invoice.total:
                    raise BusinessException(Error.RS_INSUFFICIENT_FUNDS)

                line_item_models: List[PaymentLineItemModel] = []
                for line_item in line_items:
                    line_item_models.append(PaymentLineItemModel.find_by_id(line_item.id))

                routing_slip_payment_account: PaymentAccount = PaymentAccount.find_by_id(
                    routing_slip.payment_account_id)

                cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                    routing_slip_payment_account.id)
                invoice_response = CFSService.create_account_invoice(invoice.id, line_item_models, cfs_account)

                invoice_reference: InvoiceReference = InvoiceReference.create(
                    invoice.id, invoice_response.json().get('invoice_number', None),
                    # TODO is pbc_ref_number correct?
                    invoice_response.json().get('pbc_ref_number', None))

                current_app.logger.debug('>create_invoice')

                routing_slip.remaining_amount = routing_slip.remaining_amount - decimal.Decimal(invoice.total)
                routing_slip.flush()

        else:
            invoice_reference: InvoiceReference = InvoiceReference.create(invoice.id,
                                                                          generate_transaction_number(invoice.id), None)

        current_app.logger.debug('>create_invoice')
        return invoice_reference

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Create a static receipt."""
        # Find the invoice using the invoice_number
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'{invoice_reference.invoice_number}', datetime.now(), invoice.total

    def get_payment_method_code(self):
        """Return CC as the method code."""
        return PaymentMethod.INTERNAL.value

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .payment import Payment
        from .payment_transaction import PaymentTransaction

        # Create a payment record
        current_app.logger.debug('Created payment record')
        Payment.create(payment_method=self.get_payment_method_code(),
                       payment_system=self.get_payment_system_code(),
                       payment_status=self.get_default_payment_status(),
                       invoice_number=invoice_reference.invoice_number,
                       invoice_amount=invoice.total,
                       payment_account_id=invoice.payment_account_id)

        transaction: PaymentTransaction = PaymentTransaction.create_transaction_for_invoice(
            invoice.id,
            {
                'clientSystemUrl': '',
                'payReturnUrl': ''
            }
        )
        transaction.update_transaction(transaction.id, pay_response_url=None)
