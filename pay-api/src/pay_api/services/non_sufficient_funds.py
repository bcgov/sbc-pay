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
"""Service to manage Non-Sufficient Funds."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import InvoiceSchema, NonSufficientFundsModel, NonSufficientFundsSchema
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentSchema, db
from pay_api.utils.user_context import user_context
from pay_api.utils.enums import (
    AuthHeaderType, ContentType)
from .oauth_service import OAuthService


class NonSufficientFundsService:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Service to manage Non-Sufficient Funds related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._invoice_id: int = None
        self._description: Optional[str] = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = NonSufficientFundsModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.description: str = self._dao.description

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the _id."""
        self._id = value
        self._dao.id = value

    @property
    def invoice_id(self):
        """Return the _invoice_id."""
        return self._invoice_id

    @invoice_id.setter
    def invoice_id(self, value: int):
        """Set the _invoice_id."""
        self._invoice_id = value
        self._dao.invoice_id = value

    @property
    def description(self):
        """Return the Non-Sufficient Funds description."""
        return self._description

    @description.setter
    def description(self, value: str):
        """Set the Non-Sufficient Funds description."""
        self._description = value
        self._dao.description = value

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
        """Return the Non-Sufficient Funds as a python dict."""
        non_sufficient_funds_schema = NonSufficientFundsSchema()
        d = non_sufficient_funds_schema.dump(self._dao)
        return d

    @staticmethod
    def populate(value: NonSufficientFundsModel):
        """Populate Non-Sufficient Funds Service."""
        non_sufficient_funds_service: NonSufficientFundsService = NonSufficientFundsService()
        non_sufficient_funds_service._dao = value  # pylint: disable=protected-access
        return non_sufficient_funds_service

    @staticmethod
    def save_non_sufficient_funds(invoice_id: int, description: str) -> NonSufficientFundsService:
        """Create Non-Sufficient Funds record."""
        current_app.logger.debug('<save_non_sufficient_funds')
        non_sufficient_funds_service = NonSufficientFundsService()

        non_sufficient_funds_service.invoice_id = invoice_id
        non_sufficient_funds_service.description = description
        non_sufficient_funds_dao = non_sufficient_funds_service.save()

        non_sufficient_funds_service = NonSufficientFundsService.populate(non_sufficient_funds_dao)
        current_app.logger.debug('>save_non_sufficient_funds')
        return non_sufficient_funds_service

    @staticmethod
    def query_all_non_sufficient_funds_invoices(account_id: str):
        """Return all Non-Sufficient Funds invoices."""
        query = db.session.query(PaymentModel, InvoiceModel, PaymentLineItemModel, NonSufficientFundsModel, InvoiceReferenceModel) \
            .join(InvoiceReferenceModel, PaymentModel.invoice_number == InvoiceReferenceModel.invoice_number) \
            .join(InvoiceModel, InvoiceReferenceModel.invoice_id == InvoiceModel.id) \
            .join(PaymentAccountModel, PaymentAccountModel.id == PaymentModel.payment_account_id) \
            .join(PaymentLineItemModel, PaymentLineItemModel.invoice_id == InvoiceModel.id) \
            .outerjoin(NonSufficientFundsModel, NonSufficientFundsModel.invoice_id == InvoiceModel.id) \
            .filter(PaymentAccountModel.auth_account_id == account_id) \
            .filter(PaymentModel.payment_status_code == 'FAILED') \
            .order_by(PaymentModel.id.asc())

        non_sufficient_funds_invoices = query.all()
        results, total = non_sufficient_funds_invoices, len(non_sufficient_funds_invoices)

        return results, total

    @staticmethod
    def accumulate_totals(results, payment_schema, invoice_schema):
        """Accumulate payment and invoice totals"""
        accumulated = {
            'last_payment_id': None,
            'last_invoice_id': None,
            'last_invoice_reference_id': None,
            'last_payment_line_item_id': None,
            'total_amount_to_pay': 0,
            'total_amount_paid': 0,
            'total_nsf_amount': 0,
            'total_nsf_count': 0,
            'invoices': []
        }

        for payment, invoice, payment_line_item, non_sufficient_funds, invoice_reference in results:

            if payment_line_item.id != accumulated['last_payment_line_item_id']:
                accumulated['last_payment_line_item_id'] = payment_line_item.id

            if non_sufficient_funds is not None:
                accumulated['total_nsf_count'] += 1
                accumulated['total_nsf_amount'] += float(payment_line_item.total)

            if payment.id != accumulated['last_payment_id']:
                accumulated['total_amount_paid'] += float(payment.paid_amount)
                payment_dict = payment_schema.dump(payment)
                accumulated['invoices'].append(payment_dict)
                accumulated['last_payment_id'] = payment.id

            if invoice_reference.id != accumulated['last_invoice_reference_id']:
                accumulated['last_invoice_reference_id'] = invoice_reference.id

            if invoice.id != accumulated['last_invoice_id']:
                accumulated['total_amount_to_pay'] += float(invoice.total)

                if 'invoices' not in payment_dict:
                    payment_dict['invoices'] = []

                invoice_dump = invoice_schema.dump(invoice)
                invoice_dump['created_on'] = invoice.created_on.strftime("%B %d, %Y")

                if not any(inv['id'] == invoice_dump['id'] for inv in payment_dict['invoices']):
                    payment_dict['invoices'].append(invoice_dump)

                accumulated['last_invoice_id'] = invoice.id

            else:
                invoice_dump = invoice_schema.dump(invoice)
                for inv in accumulated['invoices']:
                    if inv['id'] == invoice_dump['id']:
                        inv['invoices'].append(invoice_dump)
                        break

        return accumulated

    @staticmethod
    def find_all_non_sufficient_funds_invoices(account_id: str):
        """Return all Non-Sufficient Funds invoices."""
        results, total = NonSufficientFundsService.query_all_non_sufficient_funds_invoices(account_id=account_id)
        payment_schema = PaymentSchema()
        invoice_schema = InvoiceSchema(exclude=('receipts', 'references', '_links'))
        accumulated = NonSufficientFundsService.accumulate_totals(results, payment_schema, invoice_schema)

        data = {
            'total': total,
            'invoices': accumulated['invoices'],
            'total_amount': accumulated['total_amount_to_pay'] - accumulated['total_nsf_amount'],
            'total_amount_remaining': accumulated['total_amount_to_pay'] - accumulated['total_amount_paid'],
            'total_nsf_amount': accumulated['total_nsf_amount'],
            'total_nsf_count': accumulated['total_nsf_count']
        }

        return data

    @staticmethod
    @user_context
    def create_non_sufficient_funds_statement_pdf(account_id: str, **kwargs):
        """Create Non-Sufficient Funds statement pdf."""
        current_app.logger.debug('<generate_non_sufficient_funds_statement_pdf')
        invoice = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(account_id=account_id)
        cfs_account: CfsAccountModel = CfsAccountModel.find_by_account_id(account_id)

        account_url = current_app.config.get('AUTH_API_ENDPOINT') + f'orgs/{account_id}'
        account = OAuthService.get(endpoint=account_url,
                                    token=kwargs['user'].bearer_token,
                                    auth_header_type=AuthHeaderType.BEARER,
                                    content_type=ContentType.JSON).json()

        template_vars = {
            'suspendedOn': datetime.strptime(account['suspendedOn'], "%Y-%m-%dT%H:%M:%S%z").strftime("%B %d, %Y"),
            'accountNumber': cfs_account[0].cfs_account,
            'businessName': account['businessName'],
            'totalAmountRemaining': invoice['total_amount_remaining'],
            'totalAmount': invoice['total_amount'],
            'totalNfsAmount': invoice['total_nsf_amount'],
            'invoices': invoice['invoices']
        }
        invoice_pdf_dict = {
            'templateName': 'non_sufficient_funds',
            'reportName': 'non_sufficient_funds',
            'templateVars': template_vars,
            'populatePageNumber': True
        }
        current_app.logger.info('Invoice PDF Dict %s', invoice_pdf_dict)

        pdf_response = OAuthService.post(current_app.config.get('REPORT_API_BASE_URL'),
                                         kwargs['user'].bearer_token, AuthHeaderType.BEARER,
                                         ContentType.JSON, invoice_pdf_dict)
        current_app.logger.debug('<OAuthService responded to generate_non_sufficient_funds_statement_pdf')

        return pdf_response, invoice_pdf_dict.get('reportName')
