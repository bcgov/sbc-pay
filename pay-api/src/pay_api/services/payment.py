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
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple

from dateutil import parser
from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models.base_model import BaseModel
from pay_api.models.invoice import InvoiceSchema
from pay_api.models.invoice_reference import InvoiceReference as InvoiceReferenceModel
from pay_api.models.payment import PaymentSchema
from pay_api.models.payment_line_item import PaymentLineItem, PaymentLineItemSchema
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import (
    AuthHeaderType, Code, ContentType, InvoiceReferenceStatus, PaymentMethod, PaymentStatus, PaymentSystem)
from pay_api.utils.user_context import user_context
from pay_api.utils.util import generate_receipt_number, get_local_formatted_date, get_local_formatted_date_time
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
        self._cons_inv_number: str = None
        self._payment_date: datetime = None
        self._invoice_amount: Decimal = None
        self._paid_amount: Decimal = None
        self._receipt_number: str = None
        self._created_by: str = None
        self._paid_usd_amount: Decimal = None

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
        self.cons_inv_number: str = self._dao.cons_inv_number
        self.payment_date: datetime = self._dao.payment_date
        self.invoice_amount: Decimal = self._dao.invoice_amount
        self.paid_amount: Decimal = self._dao.paid_amount
        self.receipt_number: str = self._dao.receipt_number
        self.created_by: str = self._dao.created_by
        self.paid_usd_amount: Decimal = self._dao.paid_usd_amount

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
    def receipt_number(self):
        """Return the receipt_number."""
        return self._receipt_number

    @receipt_number.setter
    def receipt_number(self, value: str):
        """Set the receipt_number."""
        self._receipt_number = value
        self._dao.receipt_number = value

    @property
    def cons_inv_number(self):
        """Return the cons_inv_number."""
        return self._cons_inv_number

    @cons_inv_number.setter
    def cons_inv_number(self, value: str):
        """Set the cons_inv_number."""
        self._cons_inv_number = value
        self._dao.cons_inv_number = value

    @property
    def payment_date(self):
        """Return the payment_date."""
        return self._payment_date

    @payment_date.setter
    def payment_date(self, value: datetime):
        """Set the payment_date."""
        self._payment_date = value
        self._dao.payment_date = value

    @property
    def invoice_amount(self):
        """Return the invoice_amount."""
        return self._invoice_amount

    @invoice_amount.setter
    def invoice_amount(self, value: Decimal):
        """Set the amount."""
        self._invoice_amount = value
        self._dao.invoice_amount = value

    @property
    def paid_amount(self):
        """Return the paid_amount."""
        return self._paid_amount

    @paid_amount.setter
    def paid_amount(self, value: Decimal):
        """Set the amount."""
        self._paid_amount = value
        self._dao.paid_amount = value

    @property
    def created_by(self):
        """Return the created_by."""
        return self._created_by

    @created_by.setter
    def created_by(self, value: str):
        """Set the created_by."""
        self._created_by = value
        self._dao.created_by = value

    @property
    def paid_usd_amount(self):
        """Return the paid amount if it is paid in USD."""
        return self._paid_usd_amount

    @paid_usd_amount.setter
    def paid_usd_amount(self, value: Decimal):
        """Set the paid amount in USD."""
        self._paid_usd_amount = value
        self._dao.paid_usd_amount = value

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
    def create(payment_method: str, payment_system: str,  # pylint:disable=too-many-arguments
               payment_status=PaymentStatus.CREATED.value,
               invoice_number: str = None, invoice_amount: float = None, payment_account_id: int = None) -> Payment:
        """Create payment record."""
        current_app.logger.debug('<create_payment')
        p = Payment()

        p.payment_method_code = payment_method
        p.payment_status_code = payment_status
        p.payment_system_code = payment_system
        p.invoice_number = invoice_number
        p.invoice_amount = invoice_amount
        p.payment_account_id = payment_account_id
        pay_dao = p.save()

        p = Payment._populate(pay_dao)
        current_app.logger.debug('>create_payment')
        return p

    @staticmethod
    def find_by_id(identifier: int) -> Payment:
        """Find payment by id."""
        payment_dao = PaymentModel.find_by_id(identifier)
        current_app.logger.debug('>find_by_id')
        return Payment._populate(payment_dao)

    @staticmethod
    def search_account_payments(auth_account_id: str, status: str, page: int, limit: int):
        """Search account payments."""
        current_app.logger.debug('<search_account_payments')
        results, total = PaymentModel.search_account_payments(auth_account_id=auth_account_id,
                                                              payment_status=status, page=page, limit=limit)

        data = {
            'total': total,
            'page': page,
            'limit': limit,
            'items': []
        }

        # Result is tuple of payment and invoice records.
        # Iterate the results and group all invoices for the same payment by keeping the last payment object to compare.
        last_payment_iter = None
        payment_dict = {}

        for result in results:
            payment = result[0]
            invoice = result[1]
            if last_payment_iter is None or payment.id != last_payment_iter.id:  # Payment doesn't exist in array yet
                payment_schema = PaymentSchema()
                payment_dict = payment_schema.dump(payment)
                payment_dict['invoices'] = []
                inv_schema = InvoiceSchema(exclude=('receipts', 'references', '_links'))
                payment_dict['invoices'] = [inv_schema.dump(invoice)]
                data['items'].append(payment_dict)
            else:
                inv_schema = InvoiceSchema(exclude=('receipts', 'references', '_links'))
                payment_dict['invoices'].append(inv_schema.dump(invoice))

            last_payment_iter = payment

        current_app.logger.debug('>search_account_payments')
        return data

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
        for invoice_dao in purchases:
            invoice_schema = InvoiceSchema(exclude=('receipts', 'payment_line_items', 'references'))
            invoice = invoice_schema.dump(invoice_dao)
            invoice['line_items'] = []
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
        labels = ['Transaction', 'Transaction Details', 'Folio Number', 'Initiated By', 'Date', 'Purchase Amount',
                  'GST', 'Statutory Fee', 'BCOL Fee', 'Status', 'Corp Number']

        # Use the status_code_description instead of status_code.
        invoice_status_codes = CodeService.find_code_values_by_type(Code.INVOICE_STATUS.value)
        for invoice in results.get('items', None):
            filtered_codes = [cd for cd in invoice_status_codes['codes'] if
                              cd['code'] == invoice['status_code']]
            if filtered_codes:
                invoice['status_code'] = filtered_codes[0]['description']

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

                # Format date to local
                invoice['created_on'] = get_local_formatted_date(parser.parse(invoice['created_on']))

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
                ','.join([f"{detail.get('label')} {detail.get('value')}" for detail in invoice.get('details')])
                if invoice.get('details') else None,
                invoice.get('folio_number'),
                invoice.get('created_name'),
                get_local_formatted_date_time(
                    parser.parse(invoice.get('created_on')), '%Y-%m-%d %I:%M:%S %p Pacific Time'
                ),
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
            payment = Payment._populate(payment_dao)

        current_app.logger.debug('>find_payment_for_invoice')
        return payment

    @staticmethod
    def create_account_payment(auth_account_id: str, is_retry_payment: bool) -> Payment:
        """Create a payment record for the account."""
        payment: Payment = None
        if is_retry_payment:
            # If there are multiple failed payments, consolidate them
            # Else clone failed payment
            # Find all failed payments.
            payments = Payment.get_failed_payments(auth_account_id)
            can_consolidate_invoice: bool = True
            if len(payments) == 1:
                can_consolidate_invoice = False
                failed_payment = payments[0]
            else:
                # Here iterate the payments and see if there is a failed PARTIAL payment.
                for payment in payments:
                    paid_amount = payment.paid_amount or 0
                    if payment.payment_status_code == PaymentStatus.FAILED.value and paid_amount > 0:
                        failed_payment = payment
                        can_consolidate_invoice = False
                        break

            if not can_consolidate_invoice:
                # Find if there is a payment for the same invoice number, with status CREATED.
                # If yes, use that record
                # Else create new one.
                stale_payments = PaymentModel.find_payment_by_invoice_number_and_status(
                    inv_number=failed_payment.invoice_number, payment_status=PaymentStatus.CREATED.value)
                # pick the first one. Ideally only one will be there, but a race condition can cause multiple.
                if len(stale_payments) > 0:
                    payment = Payment._populate(stale_payments[0])

                # For consolidated payment status will be CREATED, if so don't create another payment record.
                elif failed_payment.payment_status_code == PaymentStatus.FAILED.value:
                    invoice_total = Decimal('0')
                    for inv in InvoiceModel.find_invoices_for_payment(payment_id=failed_payment.id):
                        invoice_total += inv.total

                    payment = Payment.create(
                        payment_method=PaymentMethod.CC.value,
                        payment_system=PaymentSystem.PAYBC.value,
                        invoice_number=failed_payment.invoice_number,
                        invoice_amount=invoice_total - (failed_payment.paid_amount or 0),
                        payment_account_id=failed_payment.payment_account_id)
                else:
                    payment = Payment._populate(failed_payment)

            else:  # Consolidate invoices into a single payment.
                payment = Payment._consolidate_payments(auth_account_id, payments)

        current_app.logger.debug('>create_account_payment')
        return payment

    @staticmethod
    def get_failed_payments(auth_account_id) -> List[PaymentModel]:
        """Return active failed payments."""
        return PaymentModel.find_payments_to_consolidate(auth_account_id=auth_account_id)

    @staticmethod
    def _populate(dao: PaymentModel):
        payment = Payment()
        payment._dao = dao  # pylint: disable=protected-access
        return payment

    @classmethod
    def _consolidate_payments(cls, auth_account_id: str, failed_payments: List[PaymentModel]) -> Payment:
        # If the payment is for consolidating failed payments,
        # 1. Cancel the invoices in CFS
        # 2. Update status of invoice_reference to CANCELLED
        # 3. Create new consolidated invoice in CFS.
        # 4. Create new invoice reference records.
        # 5. Create new payment records for the invoice as CREATED.

        pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(pay_account.id)

        consolidated_invoices: List[InvoiceModel] = []
        consolidated_line_items: List[PaymentLineItem] = []

        invoice_total = Decimal('0')
        for failed_payment in failed_payments:
            # Reverse invoice balance
            CFSService.reverse_invoice(inv_number=failed_payment.invoice_number)
            # Find all invoices for this payment.
            # Add all line items to the array
            for invoice in InvoiceModel.find_invoices_for_payment(payment_id=failed_payment.id):
                consolidated_invoices.append(invoice)
                invoice_total += invoice.total
                consolidated_line_items.append(*invoice.payment_line_items)

        # Create consolidated invoice
        invoice_response = CFSService.create_account_invoice(
            transaction_number=str(consolidated_invoices[-1].id) + '-C',
            line_items=consolidated_line_items,
            cfs_account=cfs_account)

        invoice_number: str = invoice_response.get('invoice_number')

        # Mark all invoice references to status CANCELLED, and create a new one for the new invoice number.
        for invoice in consolidated_invoices:
            inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
                invoice_id=invoice.id, status_code=InvoiceReferenceStatus.ACTIVE.value)
            inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value

            InvoiceReferenceModel(
                invoice_id=invoice.id,
                status_code=InvoiceReferenceStatus.ACTIVE.value,
                invoice_number=invoice_number,
                reference_number=invoice_response.get('pbc_ref_number')).flush()

        payment = Payment.create(
            payment_method=PaymentMethod.CC.value,
            payment_system=PaymentSystem.PAYBC.value,
            invoice_number=invoice_number,
            invoice_amount=invoice_total,
            payment_account_id=pay_account.id)

        # Update all failed payment with consolidated invoice number.
        for failed_payment in failed_payments:
            failed_payment.cons_inv_number = invoice_number
            # If the payment status is CREATED, which means we consolidated one payment which was already consolidated.
            # Set the status as DELETED
            if failed_payment.payment_status_code == PaymentStatus.CREATED.value:
                failed_payment.payment_status_code = PaymentStatus.DELETED.value

        # commit transaction
        BaseModel.commit()
        return payment

    @staticmethod
    @user_context
    def create_payment_receipt(auth_account_id: str, credit_request: Dict[str, str], **kwargs) -> Payment:
        """Create a payment record for the account."""
        pay_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(pay_account.id)
        # Create a payment record
        # Create a receipt in CFS for the  amount.
        payment = Payment.create(
            payment_method=credit_request.get('paymentMethod'),
            payment_system=PaymentSystem.PAYBC.value,
            payment_account_id=pay_account.id)
        receipt_number: str = generate_receipt_number(payment.id)
        receipt_date = credit_request.get('paymentDate')
        amount = credit_request.get('paidAmount')

        receipt_response = CFSService.create_cfs_receipt(cfs_account=cfs_account,
                                                         rcpt_number=receipt_number,
                                                         rcpt_date=receipt_date,
                                                         amount=amount,
                                                         payment_method=credit_request.get('paymentMethod'))

        payment.receipt_number = receipt_response.get('receipt_number', receipt_number)
        payment.paid_amount = amount
        payment.created_by = kwargs['user'].user_name
        payment.payment_date = parser.parse(receipt_date)
        payment.payment_status_code = PaymentStatus.COMPLETED.value
        payment.save()

        return payment
