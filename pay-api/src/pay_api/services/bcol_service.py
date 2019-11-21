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

from typing import Any, Dict, Tuple

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentSystem
from pay_api.utils.errors import Error

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class BcolService(PaymentSystemService, OAuthService):
    """Service to manage BCOL integration."""

    def create_account(self, name: str, account_info: Dict[str, Any]):
        """Create account."""
        current_app.logger.debug('<create_account')

    def get_payment_system_url(self, invoice: Invoice, inv_reference : InvoiceReference, return_url: str):
        """Return the payment system url."""
        current_app.logger.debug('<get_payment_system_url')

        current_app.logger.debug('>get_payment_system_url')

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.BCOL.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_number: int):
        """Create Invoice in PayBC."""
        current_app.logger.debug('<create_invoice')

        current_app.logger.debug('>create_invoice')

    def update_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice."""
        current_app.logger.debug('<update_invoice')

    def cancel_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug('<cancel_invoice')

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_number: str):
        """Get receipt from bcol for the receipt number or get receipt against invoice number."""
        current_app.logger.debug('<get_receipt')
