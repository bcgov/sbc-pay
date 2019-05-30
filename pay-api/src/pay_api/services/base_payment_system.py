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
from typing import Any, Dict, Tuple
from pay_api.services.payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class PaymentSystemService(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for payment system.

    This class will list the operations implemented for any payment system.
    Any payment system service SHOULD implement this class and implement the abstract methods.
    """

    def __init__(self):
        """Initialize."""
        super(PaymentSystemService, self).__init__()

    @abstractmethod
    def create_account(self, name: str, account_info: Dict[str, Any]):
        """Create account in payment system."""

    @abstractmethod
    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_number: int):
        """Create invoice in payment system."""

    @abstractmethod
    def cancel_invoice(self, account_details: Tuple[str], inv_number: str):
        """Cancel invoice in payment system."""

    @abstractmethod
    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_number: str):
        """Get receipt from payment system."""

    @abstractmethod
    def get_payment_system_code(self):
        """Return the payment system code. E.g, PAYBC, BCOL etc."""
