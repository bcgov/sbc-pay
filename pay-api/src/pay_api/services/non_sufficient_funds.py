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

from flask import current_app

from sqlalchemy import case, func

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import InvoiceSearchModel, NonSufficientFundsModel, NonSufficientFundsSchema
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import db
from pay_api.utils.converter import Converter
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceReferenceStatus, ReverseOperation
from pay_api.utils.user_context import user_context

from .oauth_service import OAuthService


class NonSufficientFundsService:
    """Service to manage Non-Sufficient Funds related operations."""

    def __init__(self):
        """Initialize the service."""
        self.dao = NonSufficientFundsModel()

    def asdict(self):
        """Return the EFT Short name as a python dict."""
        return Converter().unstructure(NonSufficientFundsSchema.from_row(self.dao))

    @staticmethod
    def populate(value: NonSufficientFundsModel):
        """Populate Non-Sufficient Funds Service."""
        non_sufficient_funds_service = NonSufficientFundsService()
        non_sufficient_funds_service.dao = value
        return non_sufficient_funds_service

    @staticmethod
    def save_non_sufficient_funds(invoice_id: int, description: str) -> NonSufficientFundsService:
        """Create Non-Sufficient Funds record."""
        current_app.logger.debug('<save_non_sufficient_funds')
        non_sufficient_funds_service = NonSufficientFundsService()

        non_sufficient_funds_service.dao.invoice_id = invoice_id
        non_sufficient_funds_service.dao.description = description
        non_sufficient_funds_dao = non_sufficient_funds_service.dao.save()

        non_sufficient_funds_service = NonSufficientFundsService.populate(non_sufficient_funds_dao)
        current_app.logger.debug('>save_non_sufficient_funds')
        return NonSufficientFundsService.asdict(non_sufficient_funds_service)

    @staticmethod
    def query_all_non_sufficient_funds_invoices(account_id: str):
        """Return all Non-Sufficient Funds invoices and their aggregate amounts."""
        query = (db.session.query(
            InvoiceModel, InvoiceReferenceModel)
            .join(InvoiceReferenceModel, InvoiceReferenceModel.invoice_id == InvoiceModel.id)
            .outerjoin(NonSufficientFundsModel, NonSufficientFundsModel.invoice_id == InvoiceModel.id)
            .join(PaymentAccountModel, PaymentAccountModel.id == InvoiceModel.payment_account_id)
            .filter(PaymentAccountModel.auth_account_id == account_id)
            .group_by(InvoiceModel.id, InvoiceReferenceModel.id)
        )

        totals_query = (db.session.query(
            func.sum(InvoiceModel.total - InvoiceModel.paid).label('total_amount_remaining'),
            func.max(case(
                [(PaymentLineItemModel.description == ReverseOperation.NSF.value, PaymentLineItemModel.total)],
                else_=0))
            .label('nsf_amount'),
            func.sum(InvoiceModel.total - case(
                [(PaymentLineItemModel.description == ReverseOperation.NSF.value, PaymentLineItemModel.total)],
                else_=0)).label('total_amount'))
            .join(PaymentAccountModel, PaymentAccountModel.id == InvoiceModel.payment_account_id)
            .join(PaymentLineItemModel, PaymentLineItemModel.invoice_id == InvoiceModel.id)
            .filter(PaymentAccountModel.auth_account_id == account_id)
        )

        aggregate_totals = totals_query.one()
        results = query.all()
        total = len(results)

        return results, total, aggregate_totals

    @staticmethod
    def find_all_non_sufficient_funds_invoices(account_id: str):
        """Return all Non-Sufficient Funds invoices."""
        results, total, aggregate_totals = NonSufficientFundsService.query_all_non_sufficient_funds_invoices(
            account_id=account_id)
        invoice_search_model = [InvoiceSearchModel.from_row(invoice_dao) for invoice_dao, _ in results]
        converter = Converter()
        invoice_list = converter.unstructure(invoice_search_model)
        new_invoices = [converter.remove_nones(invoice_dict) for invoice_dict in invoice_list]

        data = {
            'total': total,
            'invoices': new_invoices,
            'total_amount': float(aggregate_totals.total_amount),
            'total_amount_remaining': float(aggregate_totals.total_amount_remaining),
            'nsf_amount': float(aggregate_totals.nsf_amount)
        }

        return data

    @staticmethod
    @user_context
    def create_non_sufficient_funds_statement_pdf(account_id: str, **kwargs):
        """Create Non-Sufficient Funds statement pdf."""
        current_app.logger.debug('<generate_non_sufficient_funds_statement_pdf')
        invoice = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(account_id=account_id)
        cfs_account: CfsAccountModel = CfsAccountModel.find_latest_account_by_account_id(account_id)
        invoice_reference: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice['invoices'][0]['id'], InvoiceReferenceStatus.ACTIVE.value)
        account_url = current_app.config.get('AUTH_API_ENDPOINT') + f'orgs/{account_id}'
        account = OAuthService.get(
            endpoint=account_url, token=kwargs['user'].bearer_token,
            auth_header_type=AuthHeaderType.BEARER, content_type=ContentType.JSON).json()
        template_vars = {
            'suspendedOn': datetime.strptime(account['suspendedOn'], '%Y-%m-%dT%H:%M:%S%z').strftime('%B %-d, %Y'),
            'accountNumber': cfs_account.cfs_account,
            'businessName': account['businessName'],
            'totalAmountRemaining': invoice['total_amount_remaining'],
            'totalAmount': invoice['total_amount'],
            'nsfAmount': invoice['nsf_amount'],
            'invoices': invoice['invoices'],
            'invoiceNumber': invoice_reference.invoice_number,
        }

        invoice_pdf_dict = {
            'templateName': 'non_sufficient_funds',
            'reportName': 'non_sufficient_funds',
            'templateVars': template_vars,
            'populatePageNumber': True
        }
        current_app.logger.debug('Invoice PDF Dict %s', invoice_pdf_dict)

        pdf_response = OAuthService.post(current_app.config.get('REPORT_API_BASE_URL'),
                                         kwargs['user'].bearer_token, AuthHeaderType.BEARER,
                                         ContentType.JSON, invoice_pdf_dict)
        current_app.logger.debug('<OAuthService responded to generate_non_sufficient_funds_statement_pdf')

        return pdf_response, invoice_pdf_dict.get('reportName')
