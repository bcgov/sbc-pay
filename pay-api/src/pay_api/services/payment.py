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
"""Service to manage Payment model related operations."""
from datetime import datetime
from decimal import Decimal
from typing import Tuple, Dict

from dateutil import parser
from flask import current_app

from pay_api.models import Payment as PaymentModel
from pay_api.models.invoice import InvoiceSchema
from pay_api.models.payment import PaymentSchema
from pay_api.models.payment_line_item import PaymentLineItem, PaymentLineItemSchema
from pay_api.services.auth import check_auth
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.enums import ContentType, AuthHeaderType, Code
from pay_api.utils.enums import PaymentStatus
from pay_api.utils.user_context import user_context
from .code import Code as CodeService
from .oauth_service import OAuthService


class Payment:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment model related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._payment_system_code: str = None
        self._payment_method_code: str = None
        self._payment_status_code: str = None
        self._payment_account_id: int = None
        self._invoice_number: str = None
        self._completed_on: datetime = None
        self._amount: Decimal = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.payment_system_code: str = self._dao.payment_system_code
        self.payment_method_code: str = self._dao.payment_method_code
        self.payment_status_code: str = self._dao.payment_status_code
        self.payment_account_id: int = self._dao.payment_account_id
        self.invoice_number: str = self._dao.invoice_number
        self.completed_on: datetime = self._dao.completed_on
        self.amount: Decimal = self._dao.amount

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
    def payment_system_code(self):
        """Return the payment_system_code."""
        return self._payment_system_code

    @property
    def payment_method_code(self):
        """Return the payment_method_code."""
        return self._payment_method_code

    @payment_system_code.setter
    def payment_system_code(self, value: str):
        """Set the payment_system_code."""
        self._payment_system_code = value
        self._dao.payment_system_code = value

    @payment_method_code.setter
    def payment_method_code(self, value: str):
        """Set the payment_method_code."""
        self._payment_method_code = value
        self._dao.payment_method_code = value

    @property
    def payment_status_code(self):
        """Return the payment_status_code."""
        return self._payment_status_code

    @payment_status_code.setter
    def payment_status_code(self, value: str):
        """Set the payment_status_code."""
        self._payment_status_code = value
        self._dao.payment_status_code = value

    @property
    def payment_account_id(self):
        """Return the payment_account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: int):
        """Set the payment_account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def invoice_number(self):
        """Return the invoice_number."""
        return self._invoice_number

    @invoice_number.setter
    def invoice_number(self, value: str):
        """Set the invoice_number."""
        self._invoice_number = value
        self._dao.invoice_number = value

    @property
    def completed_on(self):
        """Return the completed_on."""
        return self._completed_on

    @completed_on.setter
    def completed_on(self, value: datetime):
        """Set the completed_on."""
        self._completed_on = value
        self._dao.completed_on = value

    @property
    def amount(self):
        """Return the amount."""
        return self._amount

    @amount.setter
    def amount(self, value: Decimal):
        """Set the amount."""
        self._amount = value
        self._dao.amount = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the payment as a python dict."""
        payment_schema = PaymentSchema()
        d = payment_schema.dump(self._dao)
        return d

    @staticmethod
    def create(payment_method: str, payment_system: str, payment_status=PaymentStatus.CREATED.value,
               invoice_number: str = None):
        """Create payment record."""
        current_app.logger.debug('<create_payment')
        p = Payment()

        p.payment_method_code = payment_method
        p.payment_status_code = payment_status
        p.payment_system_code = payment_system
        p.invoice_number = invoice_number
        pay_dao = p.save()
        p = Payment()
        p._dao = pay_dao  # pylint: disable=protected-access
        current_app.logger.debug('>create_payment')
        return p

    @staticmethod
    def find_by_id(identifier: int, skip_auth_check: bool = False,
                   one_of_roles: Tuple = ALL_ALLOWED_ROLES):
        """Find payment by id."""
        payment_dao = PaymentModel.find_by_id(identifier)

        # Check if user is authorized to view the payment
        if not skip_auth_check and payment_dao:
            for invoice in payment_dao.invoices:
                check_auth(invoice.business_identifier, one_of_roles=one_of_roles)

        payment = Payment()
        payment._dao = payment_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return payment

    @staticmethod
    def search_all_purchase_history(auth_account_id: str, search_filter: Dict):
        """Return all results for the purchase history."""
        return Payment.search_purchase_history(auth_account_id, search_filter, 0, 0, True)

    @classmethod
    def search_purchase_history(cls, auth_account_id: str,  # pylint: disable=too-many-locals, too-many-arguments
                                search_filter: Dict, page: int, limit: int, return_all: bool = False):
        """Search purchase history for the account."""
        current_app.logger.debug(f'<search_purchase_history {auth_account_id}')
        # If the request filter is empty, return N number of records
        # Adding offset degrades performance, so just override total records by default value if no filter is provided
        max_no_records: int = 0
        if not bool(search_filter) or not any(search_filter.values()):
            max_no_records = current_app.config.get('TRANSACTION_REPORT_DEFAULT_TOTAL')

        purchases, total = PaymentModel.search_purchase_history(auth_account_id, search_filter, page, limit, return_all,
                                                                max_no_records)
        data = {
            'total': total,
            'page': page,
            'limit': limit,
            'items': []
        }

        data = cls.create_payment_report_details(purchases, data)

        current_app.logger.debug('>search_purchase_history')
        return data

    @classmethod
    def create_payment_report_details(cls, purchases: Tuple, data: Dict):  # pylint:disable=too-many-locals
        """Return payment report details by fetching the line items.

        purchases is tuple of payment and invoice model records.
        """
        if data is None or 'items' not in data:
            data = {'items': []}

        invoice_ids = []
        invoice_status_codes = CodeService.find_code_values_by_type(Code.INVOICE_STATUS.value)
        for invoice_dao in purchases:
            invoice_schema = InvoiceSchema(exclude=('receipts', 'payment_line_items', 'references'))
            invoice = invoice_schema.dump(invoice_dao)
            invoice['line_items'] = []

            filtered_codes = [cd for cd in invoice_status_codes['codes'] if
                              cd['code'] == invoice['status_code']]
            if filtered_codes:
                invoice['status_code'] = filtered_codes[0]['description']

            data['items'].append(invoice)

            invoice_ids.append(invoice_dao.id)
        # Query the payment line item to retrieve more details
        payment_line_items = PaymentLineItem.find_by_invoice_ids(invoice_ids)
        for payment_line_item in payment_line_items:
            for invoice in data['items']:
                if invoice.get('id') == payment_line_item.invoice_id:
                    line_item_schema = PaymentLineItemSchema(many=False, exclude=('id', 'line_item_status_code'))
                    line_item_dict = line_item_schema.dump(payment_line_item)
                    line_item_dict['filing_type_code'] = payment_line_item.fee_schedule.filing_type_code
                    invoice.get('line_items').append(line_item_dict)
        return data

    @staticmethod
    def create_payment_report(auth_account_id: str, search_filter: Dict,
                              content_type: str, report_name: str):
        """Create payment report."""
        current_app.logger.debug(f'<create_payment_report {auth_account_id}')

        results = Payment.search_all_purchase_history(auth_account_id, search_filter)

        report_response = Payment.generate_payment_report(content_type, report_name, results,
                                                          template_name='payment_transactions')
        current_app.logger.debug('>create_payment_report')

        return report_response

    @staticmethod
    @user_context
    def generate_payment_report(content_type, report_name, results, template_name,
                                **kwargs):  # pylint: disable=too-many-locals
        """Prepare data and generate payment report by calling report api."""
        labels = ['Transaction', 'Folio Number', 'Initiated By', 'Date', 'Purchase Amount', 'GST', 'Statutory Fee',
                  'BCOL Fee', 'Status', 'Corp Number']
        if content_type == ContentType.CSV.value:
            template_vars = {
                'columns': labels,
                'values': Payment._prepare_csv_data(results)
            }
        else:
            total_stat_fees = 0
            total_service_fees = 0
            total = 0
            total_paid = 0

            invoices = results.get('items', None)
            for invoice in invoices:
                total += invoice.get('total', 0)
                total_stat_fees += invoice.get('total', 0) - invoice.get('service_fees', 0)

                total_service_fees += invoice.get('service_fees', 0)
                total_paid += invoice.get('paid', 0)

            account_info = None
            if kwargs.get('auth', None):
                account_id = kwargs.get('auth')['account']['id']
                contact_url = current_app.config.get('AUTH_API_ENDPOINT') + f'orgs/{account_id}/contacts'
                contact = OAuthService.get(endpoint=contact_url,
                                           token=kwargs['user'].bearer_token,
                                           auth_header_type=AuthHeaderType.BEARER,
                                           content_type=ContentType.JSON).json()

                account_info = kwargs.get('auth').get('account')
                account_info['contact'] = contact['contacts'][0]  # Get the first one from the list

            template_vars = {
                'invoices': results.get('items', None),
                'total': {
                    'statutoryFees': total_stat_fees,
                    'serviceFees': total_service_fees,
                    'fees': total,
                    'paid': total_paid,
                    'due': total - total_paid
                },
                'account': account_info,
                'statement': kwargs.get('statement')
            }

        report_payload = {
            'reportName': report_name,
            'templateName': template_name,
            'templateVars': template_vars,
            'populatePageNumber': True
        }

        report_response = OAuthService.post(endpoint=current_app.config.get('REPORT_API_BASE_URL'),
                                            token=kwargs['user'].bearer_token,
                                            auth_header_type=AuthHeaderType.BEARER,
                                            content_type=ContentType.JSON,
                                            additional_headers={'Accept': content_type},
                                            data=report_payload)
        return report_response

    @staticmethod
    def _prepare_csv_data(results):
        """Prepare data for creating a CSV report."""
        cells = []
        for invoice in results.get('items'):
            txn_description = ''
            total_gst = 0
            total_pst = 0
            for line_item in invoice.get('line_items'):
                txn_description += ',' + line_item.get('description')
                total_gst += line_item.get('gst')
                total_pst += line_item.get('pst')
            service_fee = float(invoice.get('service_fees', 0))
            total_fees = float(invoice.get('total', 0))
            row_value = [
                ','.join([line_item.get('description') for line_item in invoice.get('line_items')]),
                invoice.get('folio_number'),
                invoice.get('created_name'),
                parser.parse(invoice.get('created_on')).strftime('%m-%d-%Y %I:%M %p'),
                total_fees,
                total_gst + total_pst,
                total_fees - service_fee,  # TODO
                service_fee,
                invoice.get('status_code'),
                invoice.get('business_identifier')
            ]
            cells.append(row_value)
        return cells

    @staticmethod
    def find_payment_for_invoice(invoice_id: int):
        """Find payment for by invoice."""
        payment_dao = PaymentModel.find_payment_for_invoice(invoice_id)
        payment: Payment = None
        if payment_dao:
            payment = Payment()
            payment._dao = payment_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_payment_for_invoice')
        return payment
