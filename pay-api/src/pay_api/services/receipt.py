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
"""Service to manage Receipt."""

from datetime import datetime
from typing import Any, Dict

from flask import current_app
from sbc_common_components.utils.camel_case_response import camelcase_dict

from pay_api.exceptions import BusinessException
from pay_api.models import Payment as PaymentModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models.bcol_payment_account import BcolPaymentAccount as BcolPaymentAccountModel
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentSystem
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .oauth_service import OAuthService
from .payment_account import PaymentAccount


class Receipt():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment Line Item operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._invoice_id: int = None
        self._receipt_number: str = None
        self._receipt_date: datetime = None
        self._receipt_amount: float = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = ReceiptModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.receipt_number: str = self._dao.receipt_number
        self.receipt_date: datetime = self._dao.receipt_date
        self.receipt_amount: float = self._dao.receipt_amount

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def invoice_id(self):
        """Return the _invoice_id."""
        return self._invoice_id

    @invoice_id.setter
    def invoice_id(self, value: int):
        """Set the invoice_id."""
        self._invoice_id = value
        self._dao.invoice_id = value

    @property
    def receipt_number(self):
        """Return the _receipt_number."""
        return self._receipt_number

    @receipt_number.setter
    def receipt_number(self, value: str):
        """Set the filing_fees."""
        self._receipt_number = value
        self._dao.receipt_number = value

    @property
    def receipt_date(self):
        """Return the _receipt_date."""
        return self._receipt_date

    @receipt_date.setter
    def receipt_date(self, value: datetime):
        """Set the receipt_date."""
        self._receipt_date = value
        self._dao.receipt_date = value

    @property
    def receipt_amount(self):
        """Return the _receipt_amount."""
        return self._receipt_amount

    @receipt_amount.setter
    def receipt_amount(self, value: int):
        """Set the receipt_amount."""
        self._receipt_amount = value
        self._dao.receipt_amount = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    @staticmethod
    def find_by_id(receipt_id: int):
        """Find by receipt id."""
        receipt_dao = ReceiptModel.find_by_id(receipt_id)

        receipt = Receipt()
        receipt._dao = receipt_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return receipt

    @staticmethod
    def find_by_invoice_id_and_receipt_number(invoice_id: int, receipt_number: str = None):
        """Find by the combination of invoce id and receipt number."""
        receipt_dao = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id, receipt_number)

        receipt = Receipt()
        receipt._dao = receipt_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_invoice_id_and_receipt_number')
        return receipt

    @staticmethod
    @user_context
    def create_receipt(payment_identifier: str, invoice_identifier: str, filing_data: Dict[str, Any],
                       skip_auth_check: bool = False, **kwargs):
        """Create receipt."""
        current_app.logger.debug('<create receipt initiated')
        receipt_dict = {
            'templateName': 'payment_receipt',
            'reportName': filing_data.pop('fileName', 'payment_receipt')
        }

        template_vars = {}
        template_vars.update(filing_data)

        # invoice number not mandatory ;since only one invoice exist for a payment now
        if not invoice_identifier:
            invoice_data = Invoice.find_by_payment_identifier(payment_identifier, skip_auth_check=skip_auth_check)
        else:
            invoice_data = Invoice.find_by_id(invoice_identifier, payment_identifier, skip_auth_check=skip_auth_check)

        payment_account = PaymentAccount.find_by_pay_system_id(
            credit_account_id=invoice_data.credit_account_id,
            internal_account_id=invoice_data.internal_account_id,
            bcol_account_id=invoice_data.bcol_account_id)

        invoice_reference = InvoiceReference.find_completed_reference_by_invoice_id(invoice_data.id)

        # template_vars['incorporationNumber'] = payment_account.corp_number
        template_vars['invoiceNumber'] = invoice_reference.invoice_number

        if payment_account.payment_system_code == PaymentSystem.INTERNAL.value and invoice_data.routing_slip:
            template_vars['routingSlipNumber'] = invoice_data.routing_slip

        if not invoice_data.receipts:
            raise BusinessException(Error.INVALID_REQUEST)

        template_vars['receiptNo'] = invoice_data.receipts[0].receipt_number
        template_vars['filingIdentifier'] = filing_data.get('filingIdentifier', invoice_data.filing_id)

        if invoice_data.bcol_account_id:
            bcol_account: BcolPaymentAccountModel = BcolPaymentAccountModel.find_by_id(invoice_data.bcol_account_id)
            template_vars['bcOnlineAccountNumber'] = bcol_account.account_id

        payment_method = PaymentModel.find_payment_method_by_payment_id(payment_identifier)
        template_vars['paymentMethod'] = payment_method.description

        template_vars['invoice'] = camelcase_dict(invoice_data.asdict(), {})

        receipt_dict['templateVars'] = template_vars

        current_app.logger.debug(
            '<OAuthService invoked from receipt.py {}'.format(current_app.config.get('REPORT_API_BASE_URL')))

        pdf_response = OAuthService.post(current_app.config.get('REPORT_API_BASE_URL'),
                                         kwargs['user'].bearer_token, AuthHeaderType.BEARER,
                                         ContentType.JSON, receipt_dict)
        current_app.logger.debug('<OAuthService responded to receipt.py')

        return pdf_response
