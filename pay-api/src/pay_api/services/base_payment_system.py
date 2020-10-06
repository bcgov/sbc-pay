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
"""Abstract class for payment system implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class PaymentSystemService(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for payment system.

    This class will list the operations implemented for any payment system.
    Any payment system service SHOULD implement this class and implement the abstract methods.
    """

    def __init__(self):  # pylint: disable=useless-super-delegation
        """Initialize."""
        super(PaymentSystemService, self).__init__()

    @abstractmethod
    def create_account(self, name: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any], **kwargs):
        """Create account in payment system."""

    @abstractmethod
    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> Dict[str, Any]:
        """Create invoice in payment system."""

    @abstractmethod
    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0,
                       **kwargs):
        """Update invoice in payment system."""

    @abstractmethod
    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        """Cancel invoice in payment system."""

    @abstractmethod
    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Get receipt from payment system."""

    @abstractmethod
    def get_payment_system_url(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system portal URL for payment."""

    @abstractmethod
    def get_payment_system_code(self):
        """Return the payment system code. E.g, PAYBC, BCOL etc."""

    @abstractmethod
    def get_payment_method_code(self):
        """Return the payment method code. E.g, CC, DRAWDOWN etc."""

    @abstractmethod
    def get_default_invoice_status(self) -> str:
        """Return the default status for invoice when created."""

    @abstractmethod
    def get_default_payment_status(self) -> str:
        """Return the default status for payment when created."""

    @abstractmethod
    def complete_post_invoice(self, invoice_id: int, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
