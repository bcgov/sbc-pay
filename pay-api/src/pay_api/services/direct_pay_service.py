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
import base64
from datetime import datetime, date
from typing import Any, Dict
from urllib.parse import unquote_plus, urlencode

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models.distribution_code import DistributionCode as DistributionCodeModel
from pay_api.models.payment_line_item import PaymentLineItem as PaymentLineItemModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.hashing import HashingService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentSystem, PaymentMethod
from pay_api.utils.errors import Error
from pay_api.utils.util import parse_url_params
from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem

PAYBC_DATE_FORMAT = '%Y-%M-%d'
PAYBC_REVENUE_SEPARATOR = '|'
DECIMAL_PRECISION = '.2f'


class DirectPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_url(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        today = date.today().strftime(PAYBC_DATE_FORMAT)

        url_params_dict = {'trnDate': today,
                           'pbcRefNumber': current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER'),
                           'glDate': today,
                           'description': 'Direct Sale',
                           'trnNumber': invoice.id,
                           'trnAmount': invoice.total,
                           'paymentMethod': PaymentMethod.CC.value,
                           'redirectUri': return_url,
                           'currency': 'CAD',
                           'revenue': DirectPayService._create_revenue_string(invoice)}

        url_params = urlencode(url_params_dict)
        # unquote is used below so that unescaped url string can be hashed
        url_params_dict['hashValue'] = HashingService.encode(unquote_plus(url_params))
        encoded_query_params = urlencode(url_params_dict)  # encode it again to inlcude the hash
        paybc_url = current_app.config.get('PAYBC_DIRECT_PAY_PORTAL_URL')
        return f'{paybc_url}?{encoded_query_params}'

    @staticmethod
    def _create_revenue_string(invoice) -> str:
        payment_line_items = PaymentLineItemModel.find_by_invoice_ids([invoice.id])
        index: int = 0
        revenue_item = []
        for payment_line_item in payment_line_items:
            distribution_code = DistributionCodeModel.find_by_id(payment_line_item.fee_distribution_id)
            index = index + 1
            revenue_string = DirectPayService._get_gl_coding(distribution_code, payment_line_item.total)
            revenue_item.append(f'{index}:{revenue_string}')
            if payment_line_item.service_fees is not None and payment_line_item.service_fees > 0:
                index = index + 1
                revenue_service_fee_string = DirectPayService._get_gl_coding_for_service_fee(
                    distribution_code, payment_line_item.service_fees)
                revenue_item.append(f'{index}:{revenue_service_fee_string}')

        return PAYBC_REVENUE_SEPARATOR.join(revenue_item)

    @staticmethod
    def _get_gl_coding(distribution_code: DistributionCodeModel, total):
        return f'{distribution_code.client}.{distribution_code.responsibility_centre}.' \
            f'{distribution_code.service_line}.{distribution_code.stob}.{distribution_code.project_code}' \
            f'.000000.0000' \
            f':{format(total, DECIMAL_PRECISION)}'

    @staticmethod
    def _get_gl_coding_for_service_fee(distribution_code: DistributionCodeModel, sevice_fee):
        return f'{distribution_code.service_fee_client}.{distribution_code.service_fee_responsibility_centre}.' \
            f'{distribution_code.service_fee_line}.{distribution_code.service_fee_stob}.' \
            f'{distribution_code.service_fee_project_code}.' \
            f'000000.0000' \
            f':{format(sevice_fee, DECIMAL_PRECISION)}'
        # todo is it the right place to pad the number with traling zeros

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

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Get the receipt details by calling PayBC web service."""
        # If pay_response_url is present do all the pre-check, else check the status by using the invoice id
        if pay_response_url is not None:
            parsed_args = parse_url_params(pay_response_url)
            if not parsed_args or parsed_args.get('hashValue', None) is None:
                raise BusinessException(Error.DIRECT_PAY_INVALID_RESPONSE)

            # validate if hashValue matches with rest of the values hashed
            hash_value = parsed_args.pop('hashValue', None)[0]
            pay_response_url_without_hash = urlencode(parsed_args)
            if not HashingService.is_valid_checksum(pay_response_url_without_hash, hash_value):
                current_app.logger.warn(f'Hash not matching for pay response URL : {pay_response_url}')
                raise BusinessException(Error.DIRECT_PAY_INVALID_RESPONSE)

            # Check if trnApproved is 1=Success, 0=Declined
            trn_approved: str = parsed_args.get('trnApproved')[0]
            if trn_approved != '1':
                current_app.logger.info('Returning the receipt as the transaction is not successful')
                return None

            # Get the transaction number from args
            paybc_transaction_number = parsed_args.get('trnNumber')
        else:
            # Get the transaction number from invoice reference
            paybc_transaction_number = invoice_reference.invoice_number

        # Call PAYBC web service, get access token and use it in get txn call
        access_token = self.__get_token().json().get('access_token')

        paybc_transaction_url: str = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL')
        paybc_ref_number: str = current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')

        transaction_response = self.get(
            f'{paybc_transaction_url}/paybc/payment/{paybc_ref_number}/{paybc_transaction_number}',
            access_token, AuthHeaderType.BEARER, ContentType.JSON).json()
        if transaction_response and transaction_response.get('paymentStatus') == 'PAID':
            return transaction_response.get('trnDate'), transaction_response.get('trnAmount'), transaction_response.get(
                'trnOrderId')

        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return f'{invoice_reference.invoice_number}', datetime.now(), invoice.total

    def __get_token(self):
        """Generate oauth token from payBC which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL') + '/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('PAYBC_DIRECT_PAY_CLIENT_ID') + ':' + current_app.config.get(
                'PAYBC_DIRECT_PAY_CLIENT_SECRET'), 'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = self.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC, ContentType.FORM_URL_ENCODED,
                                   data)
        current_app.logger.debug('>Getting token')
        return token_response
