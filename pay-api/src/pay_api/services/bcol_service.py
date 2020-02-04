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
from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import AuthHeaderType, ContentType
from pay_api.utils.enums import PaymentSystem as PaySystemCode
from pay_api.utils.util import get_str_by_path

from .oauth_service import OAuthService
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

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_id: str, **kwargs):
        """Create Invoice in PayBC."""
        current_app.logger.debug('<create_invoice')
        pay_endpoint = current_app.config.get('BCOL_API_ENDPOINT') + '/payments'
        invoice_number = f'{invoice_id}-{payment_account.corp_number}'
        amount_excluding_txn_fees = sum(line.filing_fees for line in line_items)
        payload: Dict = {
            'userId': payment_account.bcol_user_id,
            'invoiceNumber': invoice_number,
            'folioNumber': kwargs.get('folio_number'),
            'amount': amount_excluding_txn_fees
        }
        pay_response = self.post(pay_endpoint, kwargs.get('jwt'), AuthHeaderType.BEARER, ContentType.JSON,
                                 payload).json()

        invoice = {
            'invoice_number': pay_response.get('key'),
            'reference_number': pay_response.get('sequenceNo'),
            'totalAmount': int(pay_response.get('totalAmount', 0))
        }
        current_app.logger.debug('>create_invoice')
        return invoice

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0):
        """Adjust the invoice."""
        current_app.logger.debug('<update_invoice')

    def cancel_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug('<cancel_invoice')

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_reference: InvoiceReference):
        """Get receipt from bcol for the receipt number or get receipt against invoice number."""
        current_app.logger.debug('<get_receipt')
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'RCPT_{invoice_reference.invoice_number}', datetime.now(), invoice.total
