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
"""Service to manage Direct Pay PAYBC Payments."""
import json
import urllib.parse

from datetime import datetime, date
from typing import Any, Dict

from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.hashing import HashingService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentSystem, PaymentMethod
from pay_api.models.distribution_code import DistributionCode as DistributionCodeModel
from pay_api.models.payment_line_item import PaymentLineItem as PaymentLineItemModel
from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem

PAYBC_DATE_FORMAT = '%Y-%M-%d'
PAYBC_REVENUE_SEPARATOR = '|'


class DirectPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_url(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        today = date.today().strftime(PAYBC_DATE_FORMAT)

        url_params = {'trnDate': today,
                      'pbcRefNumber': current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER'),
                      'glDate': today,
                      'description': 'DIRECT SALE',
                      'trnNumber': inv_ref.reference_number,
                      'trnAmount': invoice.total,
                      'paymentMethod': PaymentMethod.CC.value,
                      'redirectUri': return_url,
                      'currency': 'CAD',
                      'revenue': DirectPayService._create_revenue_string(invoice)}

        url_params['hashValue'] = HashingService.encode(json.dumps(url_params))
        encoded_query_params = urllib.parse.urlencode(url_params)
        paybc_url = current_app.config.get('PAYBC_DIRECT_PAY_PORTAL_URL')
        return f'{paybc_url}?{encoded_query_params}'

    @staticmethod
    def _create_revenue_string(invoice) -> str:
        payment_line_items = PaymentLineItemModel.find_by_invoice_ids([invoice.id])
        index: int = 0
        revenue_item = []
        for payment_line_item in payment_line_items:
            if payment_line_item.fee_schedule_id is not None:  # TODO is this logic needed???
                distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(
                    payment_line_item.fee_schedule_id)
                index = index + 1
                revenue_item.append(f'{index}:{DirectPayService._get_gl_coding(distribution_code)}')
                if payment_line_item.service_fees is not None and payment_line_item.service_fees > 0:
                    index = index + 1
                    revenue_item.append(f'{index}:{DirectPayService._get_gl_coding_for_service_fee(distribution_code)}')

        return PAYBC_REVENUE_SEPARATOR.join(revenue_item)

    @staticmethod
    def _get_gl_coding(distribution_code: DistributionCodeModel):
        return f'{distribution_code.client}:{distribution_code.responsibility_centre}:' \
               f'{distribution_code.service_line}:{distribution_code.stob}:{distribution_code.project_code}'

    @staticmethod
    def _get_gl_coding_for_service_fee(distribution_code: DistributionCodeModel):
        return f'{distribution_code.service_fee_client}:{distribution_code.service_fee_responsibility_centre}' \
               f':{distribution_code.service_fee_line}:{distribution_code.service_fee_stob}:' \
               f'{distribution_code.service_fee_project_code}'

    def get_payment_system_code(self):
        """Return DIRECT_PAY as the system code."""
        return PaymentSystem.PAYBC.value

    def get_payment_method_code(self):
        """Return DIRECT_PAY as the system code."""
        return PaymentMethod.DIRECT_PAY.value

    def create_account(self, name: str, contact_info: Dict[str, Any], authorization: Dict[str, Any], **kwargs):
        """Return an empty value since Direct Pay doesnt need any account."""
        return {}

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs):
        """Return a static invoice number for direct pay."""
        current_app.logger.debug('<create_invoice_direct_pay')

        invoice = {
            'invoice_number': f'{invoice.id}'
        }

        current_app.logger.debug('>create_invoice')
        return invoice

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0,
                       **kwargs):
        # TODO not sure if direct pay can be updated
        """Do nothing as direct payments cannot be updated as it will be completed on creation."""

    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        # TODO not sure if direct pay can be cancelled
        """Adjust the invoice to zero."""

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_reference: InvoiceReference):
        """Create a static receipt."""
        # Find the invoice using the invoice_number for direct pay
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'{invoice_reference.invoice_number}', datetime.now(), invoice.total
