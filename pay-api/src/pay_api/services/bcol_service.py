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
"""Service to manage PayBC interaction."""

from datetime import datetime
from typing import Dict

from flask import current_app
from requests.exceptions import HTTPError

from pay_api.exceptions import BusinessException, Error
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models.corp_type import CorpType
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentMethod, PaymentStatus
from pay_api.utils.enums import PaymentSystem as PaySystemCode
from pay_api.utils.errors import get_bcol_error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import generate_transaction_number

from .base_payment_system import PaymentSystemService, skip_complete_post_invoice_for_sandbox, skip_invoice_for_sandbox
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .oauth_service import OAuthService
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class BcolService(PaymentSystemService, OAuthService):
    """Service to manage BCOL integration."""

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaySystemCode.BCOL.value

    @user_context
    @skip_invoice_for_sandbox
    def create_invoice(self, payment_account: PaymentAccount,  # pylint: disable=too-many-locals
                       line_items: [PaymentLineItem], invoice: Invoice, **kwargs) -> InvoiceReference:
        """Create Invoice in PayBC."""
        current_app.logger.debug('<create_invoice')
        user: UserContext = kwargs['user']
        pay_endpoint = current_app.config.get('BCOL_API_ENDPOINT') + '/payments'
        corp_number = invoice.business_identifier
        amount_excluding_txn_fees = sum(line.total for line in line_items)
        filing_types = ','.join([item.filing_type_code for item in line_items])
        remarks = f'{corp_number}({filing_types})'
        if user.first_name:
            remarks = f'{remarks}-{user.first_name}'

        payload: Dict = {
            # 'userId': payment_account.bcol_user_id if payment_account.bcol_user_id else 'PE25020',
            'userId': payment_account.bcol_user_id,
            'invoiceNumber': generate_transaction_number(invoice.id),
            'folioNumber': invoice.folio_number,
            'amount': str(amount_excluding_txn_fees),
            'rate': str(amount_excluding_txn_fees),
            'remarks': remarks[:50],
            'feeCode': self._get_fee_code(invoice.corp_type_code, user.is_staff() or user.is_system())
        }

        if user.is_staff() or user.is_system():
            payload['userId'] = user.user_name_with_no_idp if user.is_staff() else current_app.config[
                'BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS']
            payload['accountNumber'] = invoice.bcol_account
            payload['formNumber'] = invoice.dat_number or ''
            payload['reduntantFlag'] = 'Y'
            payload['rateType'] = 'C'

        if payload.get('folioNumber', None) is None:  # Set empty folio if None
            payload['folioNumber'] = ''
        try:
            pay_response = self.post(pay_endpoint, user.bearer_token, AuthHeaderType.BEARER, ContentType.JSON,
                                     payload, raise_for_error=False)
            response_json = pay_response.json()
            current_app.logger.debug(response_json)
            pay_response.raise_for_status()
        except HTTPError as bol_err:
            current_app.logger.error(bol_err)
            error_type: str = response_json.get('type')
            if error_type.isdigit():
                error = get_bcol_error(int(error_type))
            else:
                error = Error.BCOL_ERROR
            raise BusinessException(error) from bol_err

        invoice_reference: InvoiceReference = InvoiceReference.create(invoice.id, response_json.get('key'),
                                                                      response_json.get('sequenceNo'))

        current_app.logger.debug('>create_invoice')
        return invoice_reference

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Get receipt from bcol for the receipt number or get receipt against invoice number."""
        current_app.logger.debug('<get_receipt')
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'{invoice_reference.invoice_number}', datetime.now(), invoice.total

    def _get_fee_code(self, corp_type: str, is_staff: bool = False):  # pylint: disable=no-self-use
        """Return BCOL fee code."""
        corp_type = CorpType.find_by_code(code=corp_type)
        return corp_type.bcol_staff_fee_code if is_staff else corp_type.bcol_fee_code

    def get_payment_method_code(self):
        """Return CC as the method code."""
        return PaymentMethod.DRAWDOWN.value

    def process_cfs_refund(self, invoice: InvoiceModel):
        """Process refund in CFS."""
        self._publish_refund_to_mailer(invoice)
        payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)
        payment.payment_status_code = PaymentStatus.REFUNDED.value
        payment.flush()

    @user_context
    @skip_complete_post_invoice_for_sandbox
    def complete_post_invoice(self, invoice: Invoice,  # pylint: disable=unused-argument
                              invoice_reference: InvoiceReference, **kwargs) -> None:
        """Complete any post payment activities if needed."""
        self.complete_payment(invoice, invoice_reference)
        # Publish message to the queue with payment token, so that they can release records on their side.
        self._release_payment(invoice=invoice)
