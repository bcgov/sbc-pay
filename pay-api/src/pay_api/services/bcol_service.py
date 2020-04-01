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
from typing import Any, Dict

from flask import current_app
from requests.exceptions import HTTPError

from pay_api.exceptions import BusinessException
from pay_api.models.corp_type import CorpType
from pay_api.utils.enums import AuthHeaderType, ContentType
from pay_api.utils.enums import PaymentSystem as PaySystemCode
from pay_api.utils.errors import get_bcol_error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import get_str_by_path

from .base_payment_system import PaymentSystemService
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .oauth_service import OAuthService
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class BcolService(PaymentSystemService, OAuthService):
    """Service to manage BCOL integration."""

    def create_account(self, name: str, account_info: Dict[str, Any], authorization: Dict[str, Any]):
        """Create account."""
        current_app.logger.debug('<create_account')
        bcol_user_id: str = get_str_by_path(authorization, 'account/paymentPreference/bcOnlineUserId')
        bcol_account_id: str = get_str_by_path(authorization, 'account/paymentPreference/bcOnlineAccountId')
        return {
            'bcol_account_id': bcol_account_id,
            'bcol_user_id': bcol_user_id
        }

    def get_payment_system_url(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        return None

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaySystemCode.BCOL.value

    @user_context
    def create_invoice(self, payment_account: PaymentAccount,  # pylint: disable=too-many-locals
                       line_items: [PaymentLineItem], invoice_id: str, **kwargs):
        """Create Invoice in PayBC."""
        current_app.logger.debug('<create_invoice')
        user: UserContext = kwargs['user']
        pay_endpoint = current_app.config.get('BCOL_API_ENDPOINT') + '/payments'
        corp_number = kwargs.get('business_identifier', None)
        amount_excluding_txn_fees = sum(line.filing_fees for line in line_items)
        filing_types = ','.join([item.filing_type_code for item in line_items])
        remarks = f'{corp_number}({filing_types})-{user.first_name}'
        payload: Dict = {
            # 'userId': payment_account.bcol_user_id if payment_account.bcol_user_id else 'PE25020',
            'userId': payment_account.bcol_user_id,
            'invoiceNumber': str(invoice_id),
            'folioNumber': kwargs.get('folio_number'),
            'amount': str(amount_excluding_txn_fees),
            'rate': str(amount_excluding_txn_fees),
            'remarks': remarks[:50],
            'feeCode': self._get_fee_code(kwargs.get('corp_type_code'))
        }
        try:
            pay_response = self.post(pay_endpoint, user.bearer_token, AuthHeaderType.BEARER, ContentType.JSON,
                                     payload, raise_for_error=False)
            response_json = pay_response.json()
            current_app.logger.debug(response_json)
            pay_response.raise_for_status()
        except HTTPError as bol_err:
            current_app.logger.error(bol_err)
            raise BusinessException(get_bcol_error(response_json.get('code')))

        invoice = {
            'invoice_number': response_json.get('key'),
            'reference_number': response_json.get('sequenceNo'),
            'totalAmount': -(int(response_json.get('totalAmount', 0)) / 100)
        }
        current_app.logger.debug('>create_invoice')
        return invoice

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0):
        """Adjust the invoice."""
        current_app.logger.debug('<update_invoice')

    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug('<cancel_invoice')

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_reference: InvoiceReference):
        """Get receipt from bcol for the receipt number or get receipt against invoice number."""
        current_app.logger.debug('<get_receipt')
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'RCPT_{invoice_reference.invoice_number}', datetime.now(), invoice.total

    def _get_fee_code(self, corp_type: str):  # pylint: disable=no-self-use
        """Return BCOL fee code."""
        return CorpType.find_by_code(code=corp_type).bcol_fee_code
