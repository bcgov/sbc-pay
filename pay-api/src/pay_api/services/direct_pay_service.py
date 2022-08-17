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
from urllib.parse import unquote_plus, urlencode

from dateutil import parser
from flask import current_app

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models.distribution_code import DistributionCode as DistributionCodeModel
from pay_api.models.payment_line_item import PaymentLineItem as PaymentLineItemModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.hashing import HashingService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import (
    AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentSystem)
from pay_api.utils.util import current_local_time, generate_transaction_number, parse_url_params

from ..exceptions import BusinessException
from ..utils.errors import Error
from ..utils.paybc_transaction_error_message import PAYBC_TRANSACTION_ERROR_MESSAGE_DICT
from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


PAYBC_DATE_FORMAT = '%Y-%m-%d'
PAYBC_REVENUE_SEPARATOR = '|'
DECIMAL_PRECISION = '.2f'
STATUS_PAID = ('PAID', 'CMPLT')


class DirectPayService(PaymentSystemService, OAuthService):
    """Service to manage internal payment."""

    def get_payment_system_url_for_invoice(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        today = current_local_time().strftime(PAYBC_DATE_FORMAT)
        url_params_dict = {'trnDate': today,
                           'pbcRefNumber': current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER'),
                           'glDate': today,
                           'description': 'Direct_Sale',
                           'trnNumber': generate_transaction_number(invoice.id),
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
        current_app.logger.debug(f'PayBC URL for {invoice.id} -> {paybc_url}?{encoded_query_params}')
        return f'{paybc_url}?{encoded_query_params}'

    @staticmethod
    def _create_revenue_string(invoice) -> str:
        payment_line_items = PaymentLineItemModel.find_by_invoice_ids([invoice.id])
        index: int = 0
        revenue_item = []
        for payment_line_item in payment_line_items:
            if payment_line_item.total == 0:
                continue

            distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                payment_line_item.fee_distribution_id)

            index = index + 1
            revenue_string = DirectPayService._get_gl_coding(distribution_code, payment_line_item.total)

            revenue_item.append(f'{index}:{revenue_string}')
            if payment_line_item.service_fees is not None and payment_line_item.service_fees > 0:
                index = index + 1
                service_fee: DistributionCodeModel = DistributionCodeModel.find_by_id(
                    distribution_code.service_fee_distribution_code_id)
                revenue_service_fee_string = DirectPayService._get_gl_coding(service_fee,
                                                                             payment_line_item.service_fees)
                revenue_item.append(f'{index}:{revenue_service_fee_string}')

        return PAYBC_REVENUE_SEPARATOR.join(revenue_item)

    @staticmethod
    def _get_gl_coding(distribution_code: DistributionCodeModel, total):
        return f'{distribution_code.client}.{distribution_code.responsibility_centre}.' \
               f'{distribution_code.service_line}.{distribution_code.stob}.{distribution_code.project_code}' \
               f'.000000.0000' \
               f':{format(total, DECIMAL_PRECISION)}'

    def get_payment_system_code(self):
        """Return DIRECT_PAY as the system code."""
        return PaymentSystem.PAYBC.value

    def get_payment_method_code(self):
        """Return DIRECT_PAY as the system code."""
        return PaymentMethod.DIRECT_PAY.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number for direct pay."""
        invoice_reference: InvoiceReference = InvoiceReference.create(invoice.id,
                                                                      generate_transaction_number(invoice.id), None)
        return invoice_reference

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: [PaymentLineItem], invoice_id: int, paybc_inv_number: str, reference_count: int = 0,
                       **kwargs):
        """Do nothing as direct payments cannot be updated as it will be completed on creation."""
        invoice = {
            'invoice_number': f'{invoice_id}'
        }
        return invoice

    def get_pay_system_reason_code(self, pay_response_url: str) -> str:  # pylint:disable=unused-argument
        """Return the Pay system reason code."""
        if pay_response_url is not None and 'trnApproved' in pay_response_url:
            parsed_args = parse_url_params(pay_response_url)
            trn_approved: str = parsed_args.get('trnApproved')
            # Check if trnApproved is 1=Success, 0=Declined
            if trn_approved != '1':
                # map the error code
                message_text = unquote_plus(parsed_args.get('messageText')).upper()
                pay_system_reason_code = PAYBC_TRANSACTION_ERROR_MESSAGE_DICT.get(message_text, 'GENERIC_ERROR')
                return pay_system_reason_code
        return None

    def process_cfs_refund(self, invoice: InvoiceModel):
        """Process refund in CFS."""
        current_app.logger.debug('<process_cfs_refund creating automated refund for invoice: '
                                 f'{invoice.id}, {invoice.invoice_status_code}')
        # No APPROVED invoices allowed for refund. Invoices typically land on PAID right away.
        if invoice.invoice_status_code not in (InvoiceStatus.PAID.value, InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value):
            raise BusinessException(Error.INVALID_REQUEST)

        refund_url = current_app.config.get('PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL') + '/paybc-service/api/refund'
        access_token: str = self._get_refund_token().json().get('access_token')
        data = self._build_automated_refund_payload(invoice)
        refund_response = self.post(refund_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, data).json()
        # Check if approved is 1=Success
        if refund_response.get('approved') != 1:
            message = 'Refund error: ' + refund_response.get('message')
            current_app.logger.error(message)
            raise BusinessException(Error.DIRECT_PAY_INVALID_RESPONSE)
        current_app.logger.debug('>process_cfs_refund')

    def get_receipt(self, payment_account: PaymentAccount, pay_response_url: str, invoice_reference: InvoiceReference):
        """Get the receipt details by calling PayBC web service."""
        # If pay_response_url is present do all the pre-check, else check the status by using the invoice id
        current_app.logger.debug(f'Getting receipt details {invoice_reference.invoice_id}. {pay_response_url}')
        if pay_response_url:
            parsed_args = parse_url_params(pay_response_url)

            # validate if hashValue matches with rest of the values hashed
            hash_value = parsed_args.pop('hashValue', None)
            pay_response_url_without_hash = urlencode(parsed_args)

            # Check if trnApproved is 1=Success, 0=Declined
            trn_approved: str = parsed_args.get('trnApproved')
            if trn_approved == '1' and not HashingService.is_valid_checksum(pay_response_url_without_hash, hash_value):
                current_app.logger.warning(f'Transaction is approved, but hash is not matching : {pay_response_url}')
                return None
            # Get the transaction number from args
            paybc_transaction_number = parsed_args.get('pbcTxnNumber')

        else:
            # Get the transaction number from invoice reference
            paybc_transaction_number = invoice_reference.invoice_number

        # If transaction number cannot be found, return None
        if not paybc_transaction_number:
            return None

        # Call PAYBC web service, get access token and use it in get txn call
        access_token = self.get_token().json().get('access_token')

        paybc_transaction_url: str = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL')
        paybc_ref_number: str = current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')

        transaction_response = self.get(
            f'{paybc_transaction_url}/paybc/payment/{paybc_ref_number}/{paybc_transaction_number}',
            access_token, AuthHeaderType.BEARER, ContentType.JSON, return_none_if_404=True)

        if transaction_response:
            response_json = transaction_response.json()
            if response_json.get('paymentstatus') in STATUS_PAID:
                return response_json.get('trnorderid'), parser.parse(
                    response_json.get('trndate')), float(response_json.get('trnamount'))
        return None

    def get_token(self):
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

    @classmethod
    def _get_refund_token(cls):
        """Generate seperate oauth token from PayBC which is used for automated refunds."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL') + '/paybc-service/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('PAYBC_DIRECT_PAY_CLIENT_ID') + ':' + current_app.config.get(
                'PAYBC_DIRECT_PAY_CLIENT_SECRET'), 'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = cls.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC,
                                  ContentType.FORM_URL_ENCODED,
                                  data)
        current_app.logger.debug('>Getting token')
        return token_response

    @staticmethod
    def _build_automated_refund_payload(invoice: InvoiceModel):
        """Build payload to create a refund in PAYBC."""
        receipt = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id=invoice.id)
        invoice_reference = InvoiceReferenceModel.find_reference_by_invoice_id_and_status(
            invoice.id, InvoiceReferenceStatus.COMPLETED.value)
        return {
            'orderNumber': receipt.receipt_number,
            'pbcRefNumber': current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER'),
            'txnAmount': invoice.total,
            'txnNumber': invoice_reference.invoice_number
        }
