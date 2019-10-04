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

from datetime import datetime
from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentSystem

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class InternalPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_url(self, invoice: Invoice, return_url: str):
        """Return the payment system url."""
        return None

    def get_payment_system_code(self):
        """Return INTERNAL as the system code."""
        return PaymentSystem.INTERNAL.value

    def create_account(self, name: str, account_info: Dict[str, Any]):
        """Create account internal."""
        return {}

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_number: int):
        """Return a static invoice number."""
        current_app.logger.debug('<create_invoice')

        invoice = {
            'invoice_number': f'INT_INV_{invoice_number}'
        }

        current_app.logger.debug('>create_invoice')
        return invoice

    def update_invoice(self, account_details: Tuple[str], inv_number: str):
        """Do nothing as internal payments cannot be updated as it will be completed on creation."""

    def cancel_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice to zero."""

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_number: str):
        """Create a static receipt."""
        # Find the invoice using the invoice_number
        invoice: Invoice = Invoice.find_by_invoice_number(invoice_number)
        return f'RCPT_{invoice_number}', datetime.now(), invoice.total
