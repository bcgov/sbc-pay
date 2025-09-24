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
"""Service to manage Invoice."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import InvoiceSchema, db
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.auth import check_auth
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.enums import AuthHeaderType, Code, ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context
from pay_api.utils.util import generate_transaction_number, get_local_formatted_date

from .code import Code as CodeService
from .oauth_service import OAuthService


class Invoice:
    """Service to manage Invoice related operations."""

    @staticmethod
    def asdict(dao, include_dynamic_fields: bool = False, include_links: bool = True):
        """Return the invoice as a python dict."""
        if include_links:
            invoice_schema = InvoiceSchema()
        else:
            # We need to exclude links, because the links are based on the flask context.
            invoice_schema = InvoiceSchema(
                exclude=(
                    "_links",
                    "corp_type",
                )
            )
        d = invoice_schema.dump(dao)
        Invoice._add_dynamic_fields(d, include_dynamic_fields)
        return d

    @staticmethod
    def find_by_id(identifier: int, skip_auth_check: bool = False, one_of_roles=ALL_ALLOWED_ROLES):
        """Find invoice by id."""
        invoice_dao = InvoiceModel.find_by_id(identifier)

        if not invoice_dao:
            raise BusinessException(Error.INVALID_INVOICE_ID)

        if not skip_auth_check:
            Invoice._check_for_auth(invoice_dao, one_of_roles)

        current_app.logger.debug(">find_by_id")
        return invoice_dao

    @staticmethod
    def find_invoices_for_payment(
        payment_id: int, reference_status=InvoiceReferenceStatus.ACTIVE.value
    ) -> list[Invoice]:
        """Find invoices by payment id."""
        invoices: list[Invoice] = []
        invoice_daos: list[InvoiceModel] = InvoiceModel.find_invoices_for_payment(payment_id, reference_status)

        for invoice_dao in invoice_daos:
            invoices.append(invoice_dao)

        current_app.logger.debug(">find_by_id")
        return invoices

    @staticmethod
    def find_invoices(business_identifier: str) -> dict[str, any]:
        """Find invoices by business identifier."""
        invoices: dict[str, any] = {"invoices": []}
        invoice_daos: list[InvoiceModel] = InvoiceModel.find_by_business_identifier(business_identifier)

        for invoice_dao in invoice_daos:
            invoices["invoices"].append(Invoice.asdict(invoice_dao))

        current_app.logger.debug(">find_invoices")
        return invoices

    @staticmethod
    def has_overdue_invoices(payment_account_id: int) -> bool:
        """Check if the payment account has overdue invoices."""
        query = InvoiceModel.query.filter(
            InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value,
            InvoiceModel.payment_account_id == payment_account_id,
        ).with_entities(True)
        return query.first() is not None

    @staticmethod
    @user_context
    def create_invoice_pdf(identifier: int, **kwargs) -> tuple:
        """Find invoice by id."""
        invoice_dao: InvoiceModel = InvoiceModel.find_by_id(identifier)
        if not invoice_dao:
            raise BusinessException(Error.INVALID_INVOICE_ID)

        payment_account = PaymentAccountModel.find_by_id(invoice_dao.payment_account_id)
        cfs_account = CfsAccountModel.find_by_id(invoice_dao.cfs_account_id)
        org_response = OAuthService.get(
            current_app.config.get("AUTH_API_ENDPOINT") + f"orgs/{payment_account.auth_account_id}",
            kwargs["user"].bearer_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
        ).json()
        org_contact_response = OAuthService.get(
            current_app.config.get("AUTH_API_ENDPOINT") + f"orgs/{payment_account.auth_account_id}/contacts",
            kwargs["user"].bearer_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
        ).json()

        org_contact = org_contact_response.get("contacts")[0] if org_contact_response.get("contacts", None) else {}

        invoice_number: str = (
            invoice_dao.references[0].invoice_number
            if invoice_dao.references
            else generate_transaction_number(invoice_dao.id)
        )

        filing_types: list[dict[str, str]] = []
        for line_item in invoice_dao.payment_line_items:
            business_identifier = (
                invoice_dao.business_identifier
                if invoice_dao.business_identifier and not invoice_dao.business_identifier.startswith("T")
                else ""
            )
            filing_types.append(
                {
                    "folioNumber": invoice_dao.folio_number,
                    "description": line_item.description,
                    "businessIdentifier": business_identifier,
                    "createdOn": get_local_formatted_date(invoice_dao.created_on),
                    "filingTypeCode": line_item.fee_schedule.filing_type_code,
                    "fee": line_item.total,
                    "serviceFees": line_item.service_fees,
                    "statutoryFeesGst": line_item.statutory_fees_gst,
                    "serviceFeesGst": line_item.service_fees_gst,
                    "total": line_item.total + line_item.service_fees,
                }
            )

        template_vars: dict[str, any] = {
            "invoiceNumber": invoice_number,
            "createdOn": get_local_formatted_date(invoice_dao.created_on),
            "accountNumber": cfs_account.cfs_account if cfs_account else None,
            "total": invoice_dao.total,
            "gst": invoice_dao.gst,
            "serviceFees": invoice_dao.service_fees,
            "fees": invoice_dao.total - invoice_dao.service_fees,
            "filingTypes": filing_types,
            "accountContact": {
                "name": org_response.get("name"),
                "city": org_contact.get("city", None),
                "country": org_contact.get("country", None),
                "postalCode": org_contact.get("postalCode", None),
                "region": org_contact.get("region", None),
                "street": org_contact.get("street", None),
                "streetAdditional": org_contact.get("streetAdditional", None),
            },
        }

        invoice_pdf_dict = {
            "templateName": "invoice",
            "reportName": invoice_number,
            "templateVars": template_vars,
            "populatePageNumber": True,
        }
        current_app.logger.info("Invoice PDF Dict %s", invoice_pdf_dict)
        pdf_response = OAuthService.post(
            current_app.config.get("REPORT_API_BASE_URL"),
            kwargs["user"].bearer_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            invoice_pdf_dict,
        )
        current_app.logger.debug("<OAuthService responded to receipt.py")

        return pdf_response, invoice_pdf_dict.get("reportName")

    @staticmethod
    def _check_for_auth(dao: InvoiceModel, one_of_roles=ALL_ALLOWED_ROLES):
        # Check if user is authorized to perform this action
        check_auth(dao.business_identifier, one_of_roles=one_of_roles)

    @staticmethod
    def _add_dynamic_fields(invoice: dict[str, any], calculate_dynamic_fields: bool = False) -> dict[str, any]:
        """Add calculated fields to the schema json."""
        if calculate_dynamic_fields:
            # Include redirect_for_payment flag
            redirect_for_payment: bool = False
            action_required_types = (
                PaymentMethod.DIRECT_PAY.value,
                PaymentMethod.CC.value,
                PaymentMethod.ONLINE_BANKING.value,
            )
            if (
                invoice.get("status_code") == InvoiceStatus.CREATED.value
                and invoice.get("payment_method") in action_required_types
            ):
                redirect_for_payment = True

            invoice["is_payment_action_required"] = redirect_for_payment

            # Include is online banking allowed
            if invoice.get("payment_method") == PaymentMethod.ONLINE_BANKING.value:
                online_banking_allowed = CodeService.find_code_value_by_type_and_code(
                    Code.CORP_TYPE.value, invoice.get("corp_type_code")
                ).get("is_online_banking_allowed", True)

                if online_banking_allowed:  # Check if it's a future effective filing
                    for line_item in invoice.get("line_items"):
                        if line_item.get("future_effective_fees", 0) != 0:
                            online_banking_allowed = False

                invoice["is_online_banking_allowed"] = online_banking_allowed

        return invoice

    @staticmethod
    def find_created_invoices(
        payment_method=PaymentMethod.DIRECT_PAY.value, days: int = 0, hours: int = 0, minutes: int = 0
    ):
        """Return recent invoices within a certain time and is not complete.

        Used in the batch job to find orphan records which are untouched for a time.
        """
        earliest_transaction_time = datetime.now(tz=UTC) - (timedelta(days=days, hours=hours, minutes=minutes))
        return (
            db.session.query(InvoiceModel)
            .join(InvoiceReferenceModel, InvoiceReferenceModel.invoice_id == InvoiceModel.id)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.CREATED.value)
            .filter(InvoiceModel.payment_method_code == payment_method)
            .filter(InvoiceModel.created_on >= earliest_transaction_time)
            .order_by(InvoiceModel.id.desc())
            .all()
        )
