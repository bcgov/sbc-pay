# Copyright © 2024 Province of British Columbia
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
from decimal import Decimal
import json
from typing import List, Optional
from urllib.parse import unquote_plus, urlencode

from attrs import define
from dateutil import parser
from flask import current_app
from requests import HTTPError

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RefundPartialLine
from pay_api.models.distribution_code import DistributionCode as DistributionCodeModel
from pay_api.models.payment_line_item import PaymentLineItem as PaymentLineItemModel
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.hashing import HashingService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.converter import Converter
from pay_api.utils.enums import (
    AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentDetailsGlStatus, PaymentMethod,
    PaymentSystem, RefundsPartialType)
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


@define
class RefundLineRequest():
    """Refund line from order status query."""

    revenue_account: str
    refund_amount: Decimal
    is_service_fee: bool


@define
class RefundData():
    """Refund data from order status query. From PAYBC."""

    refundglstatus: Optional[PaymentDetailsGlStatus]
    refundglerrormessage: str


@define
class RevenueLine():
    """Revenue line from order status query. From PAYBC."""

    linenumber: str
    revenueaccount: str
    revenueamount: Decimal
    glstatus: str
    glerrormessage: Optional[str]
    refund_data: List[RefundData]


@define
class OrderStatus():
    """Return from order status query from PAYBC."""

    revenue: List[RevenueLine]
    postedrefundamount: Optional[Decimal]
    refundedamount: Optional[Decimal]


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
    def _get_gl_coding(distribution_code: DistributionCodeModel, total, exclude_total=False):
        base = f'{distribution_code.client}.{distribution_code.responsibility_centre}.' \
               f'{distribution_code.service_line}.{distribution_code.stob}.{distribution_code.project_code}' \
               f'.000000.0000'
        if not exclude_total:
            base += f':{format(total, DECIMAL_PRECISION)}'
        return base

    def get_payment_system_code(self):
        """Return DIRECT_PAY as the system code."""
        return PaymentSystem.PAYBC.value

    def get_payment_method_code(self):
        """Return DIRECT_PAY as the system code."""
        return PaymentMethod.DIRECT_PAY.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: List[PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number for direct pay."""
        self.ensure_no_payment_blockers(payment_account)
        invoice_reference: InvoiceReference = InvoiceReference.create(invoice.id,
                                                                      generate_transaction_number(invoice.id), None)
        return invoice_reference

    def update_invoice(self, payment_account: PaymentAccount,  # pylint:disable=too-many-arguments
                       line_items: List[PaymentLineItem], invoice_id: int, paybc_inv_number: str,
                       reference_count: int = 0,
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

    def process_cfs_refund(self, invoice: InvoiceModel,
                           payment_account: PaymentAccount,
                           refund_partial: List[RefundPartialLine]):   # pylint:disable=unused-argument
        """Process refund in CFS."""
        current_app.logger.debug('<process_cfs_refund creating automated refund for invoice: '
                                 f'{invoice.id}, {invoice.invoice_status_code}')
        # No APPROVED invoices allowed for refund. Invoices typically land on PAID right away.
        if invoice.invoice_status_code not in \
                (InvoiceStatus.PAID.value, InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value):
            raise BusinessException(Error.INVALID_REQUEST)

        refund_url = current_app.config.get('PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL') + '/paybc-service/api/refund'
        access_token: str = self._get_refund_token().json().get('access_token')
        data = self.build_automated_refund_payload(invoice, refund_partial)

        try:
            refund_response = self.post(refund_url, access_token, AuthHeaderType.BEARER,
                                        ContentType.JSON, data, auth_header_name='Bearer-Token').json()
            # Check if approved is 1=Success
            if refund_response.get('approved') != 1:
                message = 'Refund error: ' + refund_response.get('message')
                current_app.logger.error(message)
                raise BusinessException(Error.DIRECT_PAY_INVALID_RESPONSE)

        except HTTPError as e:
            current_app.logger.error(f'PayBC Refund request failed: {str(e)}')
            error_detail = None
            error = Error.DIRECT_PAY_INVALID_RESPONSE
            if e.response:
                try:
                    error_response = json.loads(e.response.text)
                    error.detail = error_response.get('errors')
                except json.JSONDecodeError:
                    error_detail = 'Error decoding JSON response from PayBC.'
            else:
                error_detail = str(e)

            error.detail = error_detail
            raise BusinessException(error) from e

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
        token_url = current_app.config.get('PAYBC_DIRECT_PAY_CC_REFUND_BASE_URL') + '/paybc-service/oauth/token/'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('PAYBC_DIRECT_PAY_CLIENT_ID') + ':' + current_app.config.get(
                'PAYBC_DIRECT_PAY_CLIENT_SECRET'), 'utf-8')).decode('utf-8')
        token_response = cls.get(token_url, basic_auth_encoded, AuthHeaderType.BASIC,
                                 ContentType.FORM_URL_ENCODED,
                                 auth_header_name='Basic-Token')
        current_app.logger.debug('>Getting token')
        return token_response

    @staticmethod
    def _validate_refund_amount(refund_amount, max_amount):
        if refund_amount > max_amount:
            current_app.logger.error(f'Refund amount {str(refund_amount)} '
                                     f'exceeds maximum allowed amount {str(max_amount)}.')
            raise BusinessException(Error.INVALID_REQUEST)

    @staticmethod
    def _build_refund_revenue(paybc_invoice: OrderStatus, refund_lines: List[RefundLineRequest]):
        """Build PAYBC refund revenue lines for the refund."""
        if (paybc_invoice.postedrefundamount or 0) > 0 or (paybc_invoice.refundedamount or 0) > 0:
            current_app.logger.error('Refund already detected.')
            raise BusinessException(Error.INVALID_REQUEST)

        lines = []
        for line in refund_lines:
            if line.refund_amount == 0:
                continue
            # It's possible to have two payment lines with the same distribution code unfortunately.
            # For service fees, never use the first line number.

            revenue_match = next((r for r in paybc_invoice.revenue
                                  if r.revenueaccount == line.revenue_account and
                                  (line.is_service_fee and r.linenumber != '1' or line.is_service_fee is False)
                                  ), None)
            if revenue_match is None:
                current_app.logger.error('Matching distribution code to revenue account not found.')
                raise BusinessException(Error.INVALID_REQUEST)
            DirectPayService._validate_refund_amount(line.refund_amount, revenue_match.revenueamount)
            lines.append({'lineNumber': revenue_match.linenumber, 'refundAmount': line.refund_amount})
        return lines

    @staticmethod
    def _build_refund_revenue_lines(refund_partial: List[RefundPartialLine]):
        """Provide refund lines and total for the refund."""
        total = Decimal('0')
        refund_lines = []
        for refund_line in refund_partial:
            pli = PaymentLineItemModel.find_by_id(refund_line.payment_line_item_id)
            if not pli or refund_line.refund_amount < 0:
                raise BusinessException(Error.INVALID_REQUEST)
            is_service_fee = refund_line.refund_type == RefundsPartialType.SERVICE_FEES.value
            fee_distribution = DistributionCodeModel.find_by_id(pli.fee_distribution_id)
            if is_service_fee:
                DirectPayService._validate_refund_amount(refund_line.refund_amount, pli.service_fees)
                service_fee_dist_id = fee_distribution.service_fee_distribution_code_id
                fee_distribution = DistributionCodeModel.find_by_id(service_fee_dist_id)
            else:
                DirectPayService._validate_refund_amount(refund_line.refund_amount, pli.total)
            revenue_account = DirectPayService._get_gl_coding(fee_distribution,
                                                              refund_line.refund_amount,
                                                              exclude_total=True)
            refund_lines.append(RefundLineRequest(revenue_account, refund_line.refund_amount,
                                                  is_service_fee))
            total += refund_line.refund_amount
        return refund_lines, total

    @classmethod
    def _query_order_status(cls, invoice: InvoiceModel) -> OrderStatus:
        """Request invoice order status from PAYBC."""
        access_token: str = DirectPayService().get_token().json().get('access_token')
        paybc_ref_number: str = current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')
        paybc_svc_base_url = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL')
        completed_reference = list(
            filter(lambda reference: (reference.status_code == InvoiceReferenceStatus.COMPLETED.value),
                   invoice.references))[0]
        payment_url: str = \
            f'{paybc_svc_base_url}/paybc/payment/{paybc_ref_number}/{completed_reference.invoice_number}'
        payment_response = cls.get(payment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON).json()
        return Converter().structure(payment_response, OrderStatus)

    @classmethod
    def build_automated_refund_payload(cls, invoice: InvoiceModel, refund_partial: List[RefundPartialLine]):
        """Build payload to create a refund in PAYBC."""
        receipt = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id=invoice.id)
        invoice_reference = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice.id, InvoiceReferenceStatus.COMPLETED.value)
        refund_payload = {
            'orderNumber': int(receipt.receipt_number),
            'pbcRefNumber': current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER'),
            'txnAmount': invoice.total,
            'txnNumber': invoice_reference.invoice_number
        }
        if not refund_partial:
            return refund_payload

        refund_lines, total_refund = DirectPayService._build_refund_revenue_lines(refund_partial)
        paybc_invoice = DirectPayService._query_order_status(invoice)
        refund_payload.update({
            'refundRevenue': DirectPayService._build_refund_revenue(paybc_invoice, refund_lines),
            'txnAmount': total_refund
        })
        return refund_payload
