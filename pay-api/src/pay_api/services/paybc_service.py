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

import base64
import datetime
import urllib.parse
from typing import Any, Dict, Tuple

from dateutil import parser
from flask import current_app

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.constants import (
    DEFAULT_COUNTRY, DEFAULT_JURISDICTION, PAYBC_ADJ_ACTIVITY_NAME, PAYBC_BATCH_SOURCE, PAYBC_CUST_TRX_TYPE,
    PAYBC_LINE_TYPE, PAYBC_TERM_NAME)
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentSystem

from .oauth_service import OAuthService
from .payment_line_item import PaymentLineItem


class PaybcService(PaymentSystemService, OAuthService):
    """Service to manage PayBC integration."""

    def get_payment_system_url(self, invoice: Invoice, return_url: str):
        """Return the payment system url."""
        current_app.logger.debug('<get_payment_system_url')

        pay_system_url = current_app.config.get(
            'PAYBC_PORTAL_URL') + f'?inv_number={invoice.invoice_number}&pbc_ref_number={invoice.reference_number}'
        encoded_return_url = urllib.parse.quote(return_url, '')
        pay_system_url += f'&redirect_uri={encoded_return_url}'

        current_app.logger.debug('>get_payment_system_url')
        return pay_system_url

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def create_account(self, name: str, account_info: Dict[str, Any]):
        """Create account in PayBC."""
        access_token = self.__get_token().json().get('access_token')
        party = self.__create_party(access_token, name)
        account = self.__create_paybc_account(access_token, party)
        site = self.__create_site(access_token, party, account, account_info)
        return party.get('party_number'), account.get('account_number'), site.get('site_number')

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_number: int):
        """Create Invoice in PayBC."""
        current_app.logger.debug('<create_invoice')
        now = datetime.datetime.now()
        curr_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        invoice_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/invs/' \
            .format(payment_account.party_number, payment_account.account_number, payment_account.site_number)

        invoice = dict(
            batch_source=PAYBC_BATCH_SOURCE,
            cust_trx_type=PAYBC_CUST_TRX_TYPE,
            transaction_date=curr_time,
            transaction_number=f'{invoice_number}-{payment_account.corp_number}',
            gl_date=curr_time,
            term_name=PAYBC_TERM_NAME,
            comments='',
            lines=[]
        )
        index: int = 0
        for line_item in line_items:
            index = index + 1
            invoice['lines'].append(
                {
                    'line_number': index,
                    'line_type': PAYBC_LINE_TYPE,
                    'memo_line_name': current_app.config.get('PAYBC_MEMO_LINE_NAME'),
                    'description': line_item.description,
                    'attribute1': line_item.description,
                    'unit_price': line_item.total,
                    'quantity': line_item.quantity
                }
            )

        access_token = self.__get_token().json().get('access_token')
        invoice_response = self.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, invoice)

        invoice = {
            'invoice_number': invoice_response.json().get('invoice_number', None),
            'reference_number': invoice_response.json().get('pbc_ref_number', None)
        }

        current_app.logger.debug('>create_invoice')
        return invoice

    def update_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice."""
        access_token: str = self.__get_token().json().get('access_token')
        invoice = self.__get_invoice(account_details, inv_number, access_token)
        for line in invoice.get('lines'):
            amount: float = line.get('unit_price') * line.get('quantity')

            current_app.logger.debug(
                'Adding adjustment for line item : {} -- {}'.format(line.get('line_number'), amount)
            )
            self.__add_adjustment(
                account_details,
                inv_number,
                'Updating Invoice',
                amount,
                line=line.get('line_number'),
                access_token=access_token
            )
        return invoice

    def cancel_invoice(self, account_details: Tuple[str], inv_number: str):
        """Adjust the invoice to zero."""
        access_token: str = self.__get_token().json().get('access_token')
        invoice = self.__get_invoice(account_details, inv_number, access_token)
        for line in invoice.get('lines'):
            amount: float = line.get('unit_price') * line.get('quantity')

            current_app.logger.debug('Adding asjustment for line item : {} -- {}'
                                     .format(line.get('line_number'), amount))
            self.__add_adjustment(account_details, inv_number, 'Cancelling Invoice',
                                  0 - amount, line=line.get('line_number'), access_token=access_token)

    def get_receipt(self, payment_account: PaymentAccount, receipt_number: str, invoice_number: str):
        """Get receipt from paybc for the receipt number or get receipt against invoice number."""
        access_token: str = self.__get_token().json().get('access_token')
        current_app.logger.debug('<Getting receipt')
        receipt_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/rcpts/'.format(
            payment_account.party_number, payment_account.account_number, payment_account.site_number)
        if not receipt_number:  # Find all receipts for the site and then match with invoice number
            receipts_response = self.get(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON).json()
            for receipt in receipts_response.get('items'):
                expanded_receipt = self.__get_receipt_by_number(access_token, receipt_url,
                                                                receipt.get('receipt_number'))
                for invoice in expanded_receipt.get('invoices'):
                    if invoice.get('invoice_number') == invoice_number:
                        return receipt.get('receipt_number'), parser.parse(
                            expanded_receipt.get('receipt_date')), float(invoice.get('amount_applied'))

        if receipt_number:
            receipt_response = self.__get_receipt_by_number(access_token, receipt_url, receipt_number)
            receipt_date = parser.parse(receipt_response.get('receipt_date'))

            amount: float = 0
            for invoice in receipt_response.get('invoices'):
                if invoice.get('invoice_number') == invoice_number:
                    amount += float(invoice.get('amount_applied'))

            return receipt_number, receipt_date, amount
        return None

    def __get_receipt_by_number(self, access_token: str = None, receipt_url: str = None, receipt_number: str = None):
        """Get receipt details by receipt number."""
        receipt_url = receipt_url + f'{receipt_number}/'
        return self.get(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, True).json()

    def __create_party(self, access_token: str = None, party_name: str = None):
        """Create a party record in PayBC."""
        current_app.logger.debug('<Creating party Record')
        party_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/'
        party: Dict[str, Any] = {
            'customer_name': party_name
        }

        party_response = self.post(party_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, party)
        current_app.logger.debug('>Creating party Record')
        return party_response.json()

    def __create_paybc_account(self, access_token, party):
        """Create account record in PayBC."""
        current_app.logger.debug('<Creating account')
        account_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/{}/accs/'.format(
            party.get('party_number', None))
        account: Dict[str, Any] = {
            'party_number': party.get('party_number'),
            'account_description': party.get('customer_name')[:30]
        }

        account_response = self.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, account)
        current_app.logger.debug('>Creating account')
        return account_response.json()

    def __create_site(self, access_token, party, account, account_info):
        """Create site in PayBC."""
        current_app.logger.debug('<Creating site ')
        site_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/' \
            .format(account.get('party_number', None), account.get('account_number', None))
        site: Dict[str, Any] = {
            'party_number': account.get('party_number', None),
            'account_number': account.get('account_number', None),
            'site_name': party.get('customer_name') + ' Site',
            'city': account_info.get('city', None),
            'address_line_1': account_info.get('address_line_1', None),
            'postal_code': account_info.get('postal_code', None),
            'province': account_info.get('province', DEFAULT_JURISDICTION),
            'country': account_info.get('country', DEFAULT_COUNTRY),
            'customer_site_id': '1'
        }

        site_response = self.post(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, site)

        current_app.logger.debug('>Creating site ')
        return site_response.json()

    def __get_token(self):
        """Generate oauth token from payBC which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('PAYBC_BASE_URL') + '/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('PAYBC_CLIENT_ID') + ':' + current_app.config.get('PAYBC_CLIENT_SECRET'),
                  'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = self.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC, ContentType.FORM_URL_ENCODED,
                                   data)
        current_app.logger.debug('>Getting token')
        return token_response

    def __add_adjustment(self, account_details: Tuple[str],  # pylint: disable=too-many-arguments
                         inv_number: str, comment: str, amount: float, line: int = 0, access_token: str = None):
        """Add adjustment to the invoice."""
        current_app.logger.debug('>Creating PayBC Adjustment  For Invoice: ', inv_number)
        adjustment_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/invs/{}/adjs/' \
            .format(account_details[0], account_details[1], account_details[2], inv_number)
        current_app.logger.debug('>Creating PayBC Adjustment URL', adjustment_url)

        adjustment = dict(
            comment=comment,
            lines=[
                {
                    'line_number': str(line),
                    'adjustment_amount': str(amount),
                    'activity_name': PAYBC_ADJ_ACTIVITY_NAME
                }
            ]
        )

        adjustment_response = self.post(adjustment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                        adjustment)

        current_app.logger.debug('>Created PayBC Invoice Adjustment')
        return adjustment_response.json()

    def __get_invoice(self, account_details: Tuple[str], inv_number: str, access_token: str):
        """Get invoice from PayBC."""
        current_app.logger.debug('<__get_invoice')
        invoice_url = current_app.config.get('PAYBC_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/invs/{}/' \
            .format(account_details[0], account_details[1], account_details[2], inv_number)

        invoice_response = self.get(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)
        current_app.logger.debug('>__get_invoice')
        return invoice_response.json()
