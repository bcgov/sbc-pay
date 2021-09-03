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
"""Service to manage Routing Slip Payments."""
from typing import List

from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models.routing_slip import RoutingSlip as RoutingSlipModel
from pay_api.services.internal_pay_service import InternalPayService
from pay_api.services.invoice import Invoice
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentMethod
from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem
from ..exceptions import BusinessException
from ..utils.errors import Error


class RoutingSlipPayService(InternalPayService, OAuthService):
    """Service to manage routing slip related payment."""

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number."""
        current_app.logger.debug('<create_invoice')

        # check if rs has enough balance

        routing_slip = RoutingSlipModel.find_by_account_number(payment_account.id)
        if routing_slip.remaining_amount < invoice.total:
            raise BusinessException(Error.RS_INSUFFICIENT_FUNDS)

        line_item_models: List[PaymentLineItemModel] = []
        for line_item in line_items:
            line_item_models.append(PaymentLineItemModel.find_by_id(line_item.id))

        cfs_account: CfsAccountModel = CfsAccountModel.find_by_account_id(payment_account.id)
        invoice_response = CFSService.create_account_invoice(invoice.id, line_item_models, cfs_account)

        invoice_reference: InvoiceReference = InvoiceReference.create(
            invoice.id, invoice_response.json().get('invoice_number', None),
            # TODO is pbc_ref_number correct?
            invoice_response.json().get('pbc_ref_number', None))

        current_app.logger.debug('>create_invoice')

        routing_slip.remaining_amount = routing_slip.remaining_amount - invoice.total
        routing_slip.flush()

        current_app.logger.debug('>create_invoice')
        return invoice_reference

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Create a static receipt."""
        # Find the invoice using the invoice_number
        return super().get_receipt(None, None, invoice_reference=invoice_reference.invoice_id)

    def get_payment_method_code(self):
        """Return ROUTING_SLIP as the method code."""
        # TODO do we need check or cash or routing slip?
        return PaymentMethod.ROUTING_SLIP.value
