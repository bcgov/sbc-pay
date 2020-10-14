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
"""Service to manage PAYBC services."""
import base64

from flask import current_app
from pay_api.models.distribution_code import DistributionCode as DistributionCodeModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.payment import Payment as PaymentModel
from pay_api.models.payment_line_item import PaymentLineItem as PaymentLineItemModel
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod


STATUS_PAID = 'PAID'
STATUS_NOT_PROCESSED = ('PAID', 'RJCT')
DECIMAL_PRECISION = '.2f'


class DistributionTask:
    """Task to update distribution details on paybc transactions."""

    @classmethod
    def update_failed_distributions(cls):  # pylint:disable=too-many-locals
        """Update failed distributions.

        Steps:
        1. Get all invoices with status UPDATE_REVENUE_ACCOUNT.
        2. Find the completed invoice reference for the invoice.
        3. Call the paybc GET service and check if there is any revenue not processed.
        4. If yes, update the revenue details.
        5. Update the invoice status as PAID and save.
        """
        gl_updated_invoices = InvoiceModel.query.filter_by(
            invoice_status_code=InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value).all()
        current_app.logger.debug(f'Found {len(gl_updated_invoices)} invoices to update revenue details.')

        if len(gl_updated_invoices) > 0:  # pylint:disable=too-many-nested-blocks
            access_token: str = cls.__get_token().json().get('access_token')
            paybc_ref_number: str = current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')
            paybc_svc_base_url = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL')
            for gl_updated_invoice in gl_updated_invoices:
                payment: PaymentModel = PaymentModel.find_by_id(gl_updated_invoice.payment_id)
                # For now handle only GL updates for Direct Pay, more to come in future
                if payment.payment_method_code != PaymentMethod.DIRECT_PAY.value:
                    cls.__update_invoice_status(gl_updated_invoice, InvoiceStatus.PAID.value)
                else:
                    active_reference = list(
                        filter(lambda reference: (reference.status_code == InvoiceReferenceStatus.COMPLETED.value),
                               gl_updated_invoice.references))[0]
                    payment_url: str = \
                        f'{paybc_svc_base_url}/paybc/payment/{paybc_ref_number}/{active_reference.invoice_number}'

                    payment_details: dict = cls.get_payment_details(payment_url, access_token)
                    if payment_details and payment_details.get('paymentstatus') == STATUS_PAID:
                        has_gl_completed: bool = True
                        for revenue in payment_details.get('revenue'):
                            if revenue.get('glstatus') in STATUS_NOT_PROCESSED:
                                has_gl_completed = False

                        if not has_gl_completed:
                            post_revenue_payload = {
                                'revenue': []
                            }

                            invoice: InvoiceService = InvoiceService.find_by_id(identifier=gl_updated_invoice.id,
                                                                                skip_auth_check=True)

                            payment_line_items = PaymentLineItemModel.find_by_invoice_ids([invoice.id])
                            index: int = 0

                            for payment_line_item in payment_line_items:
                                distribution_code = DistributionCodeModel.find_by_id(
                                    payment_line_item.fee_distribution_id)
                                index = index + 1
                                post_revenue_payload['revenue'].append(
                                    cls.get_revenue_details(index, distribution_code, payment_line_item.total))

                                if payment_line_item.service_fees is not None and payment_line_item.service_fees > 0:
                                    index = index + 1
                                    post_revenue_payload['revenue'].append(
                                        cls.get_revenue_details(index, distribution_code,
                                                                payment_line_item.service_fees,
                                                                is_service_fee=True))

                            OAuthService.post(payment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                              post_revenue_payload)

                        cls.__update_invoice_status(gl_updated_invoice, InvoiceStatus.PAID.value)

    @classmethod
    def get_payment_details(cls, payment_url: str, access_token: str):
        """Get the receipt details by calling PayBC web service."""
        payment_response = OAuthService.get(payment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON).json()
        return payment_response

    @classmethod
    def get_revenue_details(cls, index: int, dist_code: DistributionCodeModel, amount: float,
                            is_service_fee: bool = False):
        """Get the receipt details by calling PayBC web service."""
        if is_service_fee:
            revenue_account = f'{dist_code.service_fee_client}.{dist_code.service_fee_responsibility_centre}.' \
                f'{dist_code.service_fee_line}.{dist_code.service_fee_stob}.{dist_code.service_fee_project_code}' \
                f'.000000.0000'
        else:
            revenue_account = f'{dist_code.client}.{dist_code.responsibility_centre}.' \
                f'{dist_code.service_line}.{dist_code.stob}.{dist_code.project_code}' \
                f'.000000.0000'

        return {
            'lineNumber': str(index),
            'revenueAccount': revenue_account,
            'revenueAmount': format(amount, DECIMAL_PRECISION)
        }

    @classmethod
    def __get_token(cls):
        """Generate oauth token from payBC which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('PAYBC_DIRECT_PAY_BASE_URL') + '/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('PAYBC_DIRECT_PAY_CLIENT_ID') + ':' + current_app.config.get(
                'PAYBC_DIRECT_PAY_CLIENT_SECRET'), 'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = OAuthService.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC,
                                           ContentType.FORM_URL_ENCODED,
                                           data)
        current_app.logger.debug('>Getting token')
        return token_response

    @classmethod
    def __update_invoice_status(cls, gl_updated_invoice, status: str):
        gl_updated_invoice.invoice_status_code = status
        gl_updated_invoice.save()
        current_app.logger.info(f'Updated invoice : {gl_updated_invoice.id}')
