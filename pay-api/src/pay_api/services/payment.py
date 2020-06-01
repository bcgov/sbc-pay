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


class Payment:  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment model related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._payment_system_code: str = None
        self._payment_method_code: str = None
        self._payment_status_code: str = None
        self._invoices = None

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
        self.invoices = self._dao.invoices

    @property
    def id(self):
        """Return the _id."""
        return self._id

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

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

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
    def invoices(self):
        """Return the payment invoices."""
        return self._invoices

    @invoices.setter
    def invoices(self, value):
        """Set the invoices."""
        self._invoices = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the payment as a python dict."""
        payment_schema = PaymentSchema()
        d = payment_schema.dump(self._dao)
        return d

    @staticmethod
    def create(payment_method: str, payment_system: str = 'CC'):
        """Create payment record."""
        current_app.logger.debug('<create_payment')
        p = Payment()
        p.payment_method_code = payment_method
        p.payment_status_code = PaymentStatus.CREATED.value
        p.payment_system_code = payment_system
        pay_dao = p.flush()
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

    @staticmethod
    def search_purchase_history(auth_account_id: str, search_filter: Dict, page: int,  # pylint: disable=too-many-locals
                                limit: int, return_all: bool = False):
        """Search purchase history for the account."""
        current_app.logger.debug(f'<search_purchase_history {auth_account_id}')
        purchases, total = PaymentModel.search_purchase_history(auth_account_id, search_filter, page, limit, return_all)
        data = {
            'total': total,
            'page': page,
            'limit': limit,
            'items': []
        }

        invoice_ids = []
        payment_status_codes = CodeService.find_code_values_by_type(Code.PAYMENT_STATUS.value)
        for purchase in purchases:
            payment_dao = purchase[0]
            invoice_dao = purchase[1]
            payment_schema = PaymentSchema(exclude=('invoices', 'transactions', '_links', 'created_by', 'updated_by'))
            purchase_history = payment_schema.dump(payment_dao)

            filtered_codes = [cd for cd in payment_status_codes['codes'] if
                              cd['code'] == purchase_history['status_code']]
            if filtered_codes:
                purchase_history['status_code'] = filtered_codes[0]['description']

            invoice_schema = InvoiceSchema(exclude=('receipts', 'payment_line_items', 'references', '_links',
                                                    'created_by', 'created_name', 'created_on', 'updated_by',
                                                    'updated_name', 'updated_on', 'invoice_status_code'))
            invoice = invoice_schema.dump(invoice_dao)
            invoice['line_items'] = []
            purchase_history['invoice'] = invoice
            data['items'].append(purchase_history)

            invoice_ids.append(invoice_dao.id)

        # Query the payment line item to retrieve more details
        payment_line_items = PaymentLineItem.find_by_invoice_ids(invoice_ids)
        for payment_line_item in payment_line_items:
            for purchase_history in data['items']:
                if purchase_history.get('invoice').get('id') == payment_line_item.invoice_id:
                    line_item_schema = PaymentLineItemSchema(many=False, exclude=('id', 'line_item_status_code'))
                    line_item_dict = line_item_schema.dump(payment_line_item)
                    line_item_dict['filing_type_code'] = payment_line_item.fee_schedule.filing_type_code
                    purchase_history.get('invoice').get('line_items').append(line_item_dict)

        current_app.logger.debug('>search_purchase_history')
        return data

    @staticmethod
    @user_context
    def create_payment_report(auth_account_id: str, search_filter: Dict,  # pylint: disable=too-many-locals
                              content_type: str, report_name: str, **kwargs):
        """Create payment report."""
        current_app.logger.debug(f'<create_payment_report {auth_account_id}')

        labels = ['Transaction', 'Folio Number', 'Initiated By', 'Date', 'Purchase Amount', 'GST', 'Statutory Fee',
                  'BCOL Fee', 'Status', 'Corp Number']

        results = Payment.search_all_purchase_history(auth_account_id, search_filter)

        report_payload = {
            'reportName': report_name,
            'templateName': 'payment_transactions',
            'templateVars': {
                'columns': labels,
                'values': []
            }
        }

        for item in results.get('items'):
            invoice = item.get('invoice')
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
                item.get('created_name'),
                parser.parse(item.get('created_on')).strftime('%Y-%m-%d %I:%M %p'),
                total_fees,
                total_gst + total_pst,
                total_fees - service_fee,  # TODO
                service_fee,
                item.get('status_code'),
                invoice.get('business_identifier')
            ]
            report_payload['templateVars']['values'].append(row_value)

        report_response = OAuthService.post(endpoint=current_app.config.get('REPORT_API_BASE_URL'),
                                            token=kwargs['user'].bearer_token,
                                            auth_header_type=AuthHeaderType.BEARER,
                                            content_type=ContentType.JSON,
                                            additional_headers={'Accept': content_type},
                                            data=report_payload)
        current_app.logger.debug('>create_payment_report')

        return report_response
