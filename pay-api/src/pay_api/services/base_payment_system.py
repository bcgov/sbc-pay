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

from flask import current_app
from sentry_sdk import capture_message

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment import Payment
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import InvoiceStatus, PaymentStatus, TransactionStatus
from pay_api.utils.util import get_pay_subject_name

from .payment_line_item import PaymentLineItem


class PaymentSystemService(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for payment system.

    This class will list the operations implemented for any payment system.
    Any payment system service SHOULD implement this class and implement the abstract methods.
    """

    def __init__(self):
        """Initialize."""
        super().__init__(self)

    def create_account(self, name: str, contact_info: Dict[str, Any],  # pylint: disable=unused-argument, no-self-use
                       payment_info: Dict[str, Any],  # pylint: disable=unused-argument
                       **kwargs) -> CfsAccountModel:
        """Create account in payment system."""
        return None

    def update_account(self, name: str, cfs_account: CfsAccountModel,  # pylint: disable=unused-argument, no-self-use
                       payment_info: Dict[str, Any]) -> CfsAccountModel:  # pylint: disable=unused-argument
        """Update account in payment system."""
        return None

    @abstractmethod
    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Create invoice in payment system."""

    def update_invoice(self,  # pylint:disable=too-many-arguments,no-self-use,unused-argument
                       payment_account: PaymentAccount,  # pylint: disable=unused-argument
                       line_items: [PaymentLineItem], invoice_id: int,  # pylint: disable=unused-argument
                       paybc_inv_number: str, reference_count: int = 0,  # pylint: disable=unused-argument
                       **kwargs):
        """Update invoice in payment system."""
        return None

    def cancel_invoice(self, payment_account: PaymentAccount,  # pylint:disable=unused-argument, no-self-use
                       inv_number: str):  # pylint: disable=unused-argument
        """Cancel invoice in payment system."""
        return None

    def get_receipt(self, payment_account: PaymentAccount,  # pylint:disable=unused-argument, no-self-use
                    pay_response_url: str, invoice_reference: InvoiceReference):  # pylint: disable=unused-argument
        """Get receipt from payment system."""
        return None

    def get_payment_system_url_for_invoice(self, invoice: Invoice,  # pylint:disable=unused-argument, no-self-use
                                           inv_ref: InvoiceReference,  # pylint: disable=unused-argument
                                           return_url: str) -> str:  # pylint: disable=unused-argument
        """Return the payment system portal URL for payment."""
        return None

    def get_payment_system_url_for_payment(self, payment: Payment,  # pylint:disable=unused-argument, no-self-use
                                           inv_ref: InvoiceReference,  # pylint: disable=unused-argument
                                           return_url: str) -> str:  # pylint: disable=unused-argument
        """Return the payment system portal URL for payment."""
        return None

    def get_pay_system_reason_code(self, pay_response_url: str) -> str:  # pylint:disable=unused-argument, no-self-use
        """Return the Pay system reason code."""
        return None

    @abstractmethod
    def get_payment_system_code(self):
        """Return the payment system code. E.g, PAYBC, BCOL etc."""

    @abstractmethod
    def get_payment_method_code(self):
        """Return the payment method code. E.g, CC, DRAWDOWN etc."""

    def get_default_invoice_status(self) -> str:  # pylint: disable=no-self-use
        """Return the default status for invoice when created."""
        return InvoiceStatus.CREATED.value

    def get_default_payment_status(self) -> str:  # pylint: disable=no-self-use
        """Return the default status for payment when created."""
        return PaymentStatus.CREATED.value

    def complete_post_invoice(self, invoice: Invoice,  # pylint: disable=unused-argument, no-self-use
                              invoice_reference: InvoiceReference) -> None:  # pylint: disable=unused-argument
        """Complete any post invoice activities if needed."""
        return None

    def apply_credit(self, invoice: Invoice) -> None:  # pylint:disable=unused-argument, no-self-use
        """Apply credit on invoice."""
        return None

    @staticmethod
    def _release_payment(invoice: Invoice):
        """Release record."""
        from .payment_transaction import publish_response  # pylint:disable=import-outside-toplevel,cyclic-import
        from .payment_transaction import PaymentTransaction  # pylint:disable=import-outside-toplevel,cyclic-import

        payload = PaymentTransaction.create_event_payload(invoice, TransactionStatus.COMPLETED.value)
        try:
            publish_response(payload=payload, subject=get_pay_subject_name(invoice.corp_type_code))
        except Exception as e:  # NOQA pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.error('Notification to Queue failed for the Payment Event %s', payload)
            capture_message('Notification to Queue failed for the Payment Event : {msg}.'.format(msg=payload),
                            level='error')
