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
"""Service to manage Non-Sufficient Funds."""
from __future__ import annotations

from datetime import datetime

from flask import current_app
from sqlalchemy import case, func

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import InvoiceSearchModel, NonSufficientFunds, NonSufficientFundsSchema
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Statement as StatementModel, StatementDTO
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import db
from pay_api.utils.converter import Converter
from pay_api.utils.enums import (
    AuthHeaderType, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, ReverseOperation)
from pay_api.utils.user_context import user_context

from .oauth_service import OAuthService


class NonSufficientFundsService:
    """Service to manage Non-Sufficient Funds related operations."""

    def __init__(self):
        """Initialize the service."""
        self.dao = NonSufficientFunds()

    def asdict(self):
        """Return the EFT Short name as a python dict."""
        return Converter().unstructure(NonSufficientFundsSchema.from_row(self.dao))

    @staticmethod
    def populate(value: NonSufficientFunds):
        """Populate Non-Sufficient Funds Service."""
        non_sufficient_funds_service = NonSufficientFundsService()
        non_sufficient_funds_service.dao = value
        return non_sufficient_funds_service

    @staticmethod
    def save_non_sufficient_funds(invoice_id: int, invoice_number: str, cfs_account: int,
                                  description: str) -> NonSufficientFundsService:
        """Create Non-Sufficient Funds record."""
        current_app.logger.debug('<save_non_sufficient_funds')
        non_sufficient_funds_service = NonSufficientFundsService()

        non_sufficient_funds_service.dao.description = description
        non_sufficient_funds_service.dao.invoice_id = invoice_id
        non_sufficient_funds_service.dao.invoice_number = invoice_number
        non_sufficient_funds_service.dao.cfs_account = cfs_account
        non_sufficient_funds_dao = non_sufficient_funds_service.dao.save()

        non_sufficient_funds_service = NonSufficientFundsService.populate(non_sufficient_funds_dao)
        current_app.logger.debug('>save_non_sufficient_funds')
        return NonSufficientFundsService.asdict(non_sufficient_funds_service)

    @staticmethod
    def exists_for_invoice_number(invoice_number: str) -> bool:
        """Return boolean if a row exists for the invoice number."""
        return (db.session.query(NonSufficientFunds)
                .filter(NonSufficientFunds.invoice_number == invoice_number)
                .count()
                ) > 0

    @staticmethod
    def query_all_non_sufficient_funds_invoices(account_id: str):
        """Return all Non-Sufficient Funds invoices and their aggregate amounts."""
        query = (db.session.query(
            InvoiceModel, InvoiceReferenceModel)
            .join(InvoiceReferenceModel, InvoiceReferenceModel.invoice_id == InvoiceModel.id)
            .join(NonSufficientFunds,
                  NonSufficientFunds.invoice_number == InvoiceReferenceModel.invoice_number)
            .join(PaymentAccountModel, PaymentAccountModel.id == InvoiceModel.payment_account_id)
            .filter(PaymentAccountModel.auth_account_id == account_id,
                    InvoiceModel.invoice_status_code != InvoiceStatus.PAID.value)
            .distinct(InvoiceModel.id)
            .group_by(InvoiceModel.id, InvoiceReferenceModel.id)
        )

        invoice_totals_subquery = (
            db.session.query(
                InvoiceModel.id.label('invoice_id'),
                (InvoiceModel.total - InvoiceModel.paid).label('amount_remaining'),
                func.max(case(
                    (PaymentLineItemModel.description == ReverseOperation.NSF.value, PaymentLineItemModel.total),
                    else_=0)).label('nsf_amount')
            )
            .join(InvoiceReferenceModel, InvoiceReferenceModel.invoice_id == InvoiceModel.id)
            .join(NonSufficientFunds,
                  NonSufficientFunds.invoice_number == InvoiceReferenceModel.invoice_number)
            .join(PaymentAccountModel, PaymentAccountModel.id == InvoiceModel.payment_account_id)
            .join(PaymentLineItemModel, PaymentLineItemModel.invoice_id == InvoiceModel.id)
            .filter(PaymentAccountModel.auth_account_id == account_id,
                    InvoiceModel.invoice_status_code != InvoiceStatus.PAID.value)
            .group_by(InvoiceModel.id)
            .subquery()
        )

        totals_query = (
            db.session.query(
                func.sum(invoice_totals_subquery.c.amount_remaining).label('total_amount_remaining'),
                func.sum(invoice_totals_subquery.c.nsf_amount).label('nsf_amount'),
                func.sum(invoice_totals_subquery.c.amount_remaining - invoice_totals_subquery.c.nsf_amount)
                .label('total_amount')
            )
        )

        statement_ids_query = db.session.query(StatementInvoicesModel.statement_id) \
            .filter(StatementInvoicesModel.invoice_id.in_(query.with_entities(InvoiceModel.id))) \
            .distinct(StatementInvoicesModel.statement_id)
        statements = db.session.query(StatementModel) \
            .filter(StatementModel.id.in_(statement_ids_query)) \
            .all()

        aggregate_totals = totals_query.one()
        results = query.all()
        total = len(results)

        return results, total, aggregate_totals, statements

    @staticmethod
    def find_all_non_sufficient_funds_invoices(account_id: str):
        """Return all Non-Sufficient Funds invoices."""
        results, total, aggregate_totals, statements = \
            NonSufficientFundsService.query_all_non_sufficient_funds_invoices(account_id=account_id)
        invoice_search_model = [InvoiceSearchModel.from_row(invoice_dao) for invoice_dao, _ in results]
        invoices = Converter().unstructure(invoice_search_model)
        invoices = [Converter().remove_nones(invoice_dict) for invoice_dict in invoices]
        statements = StatementDTO.dao_to_dict(statements)
        data = {
            'total': total,
            'invoices': invoices,
            'statements': statements,
            'total_amount': float(aggregate_totals.total_amount or 0),
            'total_amount_remaining': float(aggregate_totals.total_amount_remaining or 0),
            'nsf_amount': float(aggregate_totals.nsf_amount or 0)
        }

        return data

    @staticmethod
    @user_context
    def create_non_sufficient_funds_statement_pdf(account_id: str, **kwargs):
        """Create Non-Sufficient Funds statement pdf."""
        current_app.logger.debug('<generate_non_sufficient_funds_statement_pdf')
        invoice = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(account_id=account_id)
        payment_account = PaymentAccountModel.find_by_auth_account_id(account_id)
        cfs_account = CfsAccountModel.find_latest_by_payment_method(payment_account.id, PaymentMethod.PAD.value)
        invoice_reference: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice['invoices'][0]['id'], InvoiceReferenceStatus.ACTIVE.value)
        account_url = current_app.config.get('AUTH_API_ENDPOINT') + f'orgs/{account_id}'
        account = OAuthService.get(
            endpoint=account_url, token=kwargs['user'].bearer_token,
            auth_header_type=AuthHeaderType.BEARER, content_type=ContentType.JSON).json()
        template_vars = {
            'suspendedOn': datetime.strptime(account['suspendedOn'], '%Y-%m-%dT%H:%M:%S%z')
            .strftime('%B %-d, %Y') if 'suspendedOn' in account else None,
            'accountNumber': cfs_account.cfs_account,
            'businessName': account.get('businessName', account.get('createdBy')),
            'totalAmountRemaining': invoice['total_amount_remaining'],
            'totalAmount': invoice['total_amount'],
            'nsfAmount': invoice['nsf_amount'],
            'invoices': invoice['invoices'],
            'invoiceNumber': getattr(invoice_reference, 'invoice_number', None)
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
