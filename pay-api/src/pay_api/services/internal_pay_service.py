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
from http import HTTPStatus

from flask import current_app

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem, RoutingSlipStatus
from pay_api.utils.util import generate_transaction_number

from ..exceptions import BusinessException
from ..utils.errors import Error
from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class InternalPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_code(self):
        """Return INTERNAL as the system code."""
        return PaymentSystem.INTERNAL.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number."""
        current_app.logger.debug('<create_invoice')
        routing_slip = None
        is_zero_dollar_invoice = invoice.total == 0
        invoice_reference: InvoiceReference = None
        if routing_slip_number := invoice.routing_slip:
            routing_slip = RoutingSlipModel.find_by_number(routing_slip_number)
            InternalPayService._validate_routing_slip(routing_slip, invoice)
        if not is_zero_dollar_invoice and routing_slip is not None:
            # creating invoice in cfs is done in job
            routing_slip.remaining_amount = routing_slip.remaining_amount - decimal.Decimal(invoice.total)
            routing_slip.flush()
        else:
            invoice_reference = InvoiceReference.create(invoice.id,
                                                        generate_transaction_number(invoice.id), None)
            invoice.invoice_status_code = InvoiceStatus.CREATED.value
            invoice.save()

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
        if invoice.invoice_status_code != InvoiceStatus.APPROVED.value:
            self.complete_payment(invoice, invoice_reference)
            # Publish message to the queue with payment token, so that they can release records on their side.
        self._release_payment(invoice=invoice)

    def get_default_invoice_status(self) -> str:  # pylint: disable=no-self-use
        """Return the default status for invoice when created."""
        return InvoiceStatus.APPROVED.value

    def process_cfs_refund(self, invoice: InvoiceModel):
        """Process refund in CFS."""
        # TODO handle Routing Slip refund CAS integration here
        if invoice.total == 0:
            raise BusinessException(Error.NO_FEE_REFUND)

        # find if its a routing slip refund
        # if yes -> check existing one or legacy
        # if yes , add money back to rs after refunding

        if (routing_slip_number := invoice.routing_slip) is None:
            raise BusinessException(Error.INVALID_REQUEST)
        if invoice.total == 0:
            raise BusinessException(Error.NO_FEE_REFUND)
        if not (routing_slip := RoutingSlipModel.find_by_number(routing_slip_number)):
            raise BusinessException(Error.ROUTING_SLIP_REFUND)

        payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)
        if payment:
            payment.payment_status_code = PaymentStatus.REFUNDED.value
            payment.flush()
        routing_slip.remaining_amount += decimal.Decimal(invoice.total)
        routing_slip.flush()
        invoice.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
        invoice.flush()

    @staticmethod
    def _validate_routing_slip(routing_slip: RoutingSlipModel, invoice: Invoice):
        """Validate different conditions of a routing slip payment."""
        # is rs doesnt exist , legacy routing slip flag should be on
        if routing_slip is None:
            if not current_app.config.get('ALLOW_LEGACY_ROUTING_SLIPS'):
                raise BusinessException(Error.RS_DOESNT_EXIST)
            # legacy routing slip which doesnt exist in the system.No validations
            return

        # check rs is nsf
        if routing_slip.status == RoutingSlipStatus.NSF.value and routing_slip.remaining_amount <= 0:
            raise BusinessException(Error.RS_INSUFFICIENT_FUNDS)

        # check rs is active
        if routing_slip.status not in (
                RoutingSlipStatus.ACTIVE.value, RoutingSlipStatus.LINKED.value, RoutingSlipStatus.NSF.value):
            raise BusinessException(Error.RS_NOT_ACTIVE)

        if routing_slip.parent:
            detail = f'This Routing slip is linked, enter the parent Routing slip: {routing_slip.parent.number}'
            raise BusinessException(InternalPayService._create_error_object('LINKED_ROUTING_SLIP', detail))
        if routing_slip.remaining_amount < invoice.total:
            detail = f'There is not enough balance in this Routing slip. ' \
                     f'The current balance is: ${routing_slip.remaining_amount:.2f}'

            raise BusinessException(InternalPayService.
                                    _create_error_object('INSUFFICIENT_BALANCE_IN_ROUTING_SLIP', detail))

    @staticmethod
    def _create_error_object(code: str, detail: str):
        return type('obj', (object,),
                    {'code': code, 'status': HTTPStatus.BAD_REQUEST,
                     'detail': detail})()
