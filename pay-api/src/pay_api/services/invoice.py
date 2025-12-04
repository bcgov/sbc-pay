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
from decimal import Decimal  # noqa: TC003

import pytz
from flask import abort, current_app
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceCompositeModel, InvoiceSchema, InvoiceSearchModel, db
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.auth import check_auth
from pay_api.services.code import Code as CodeService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.constants import ALL_ALLOWED_ROLES, DT_SHORT_FORMAT
from pay_api.utils.enums import (
    AuthHeaderType,
    Code,
    ContentType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    Role,
    RolePattern,
)
from pay_api.utils.errors import Error
from pay_api.utils.product_auth_util import ProductAuthUtil
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import (
    generate_transaction_number,
    get_first_and_last_dates_of_month,
    get_local_formatted_date,
    get_str_by_path,
    get_week_start_and_end_date,
)


class Invoice:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Service to manage Invoice related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._invoice_status_code: str = None
        self._payment_account_id: str = None
        self._bcol_account: str = None
        self._total = None
        self._paid = None
        self._refund = None
        self._payment_date: datetime | None = None
        self._refund_date: datetime | None = None
        self._payment_line_items = None
        self._corp_type_code = None
        self._receipts = None
        self._routing_slip: str = None
        self._filing_id: str = None
        self._folio_number: str = None
        self._service_fees = None
        self._business_identifier: str = None
        self._dat_number: str = None
        self._cfs_account_id: int
        self._payment_method_code: str = None
        self._details: dict = None
        self._gst = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = InvoiceModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.payment_method_code: int = self._dao.payment_method_code
        self.invoice_status_code: str = self._dao.invoice_status_code
        self.bcol_account: str = self._dao.bcol_account
        self.payment_account_id: str = self._dao.payment_account_id
        self.refund: Decimal = self._dao.refund
        self.payment_date: datetime = self._dao.payment_date
        self.refund_date: datetime = self._dao.refund_date
        self.total: Decimal = self._dao.total
        self.paid: Decimal = self._dao.paid
        self.payment_line_items = self._dao.payment_line_items
        self.corp_type_code = self._dao.corp_type_code
        self.receipts = self._dao.receipts
        self.routing_slip: str = self._dao.routing_slip
        self.filing_id: str = self._dao.filing_id
        self.folio_number: str = self._dao.folio_number
        self.service_fees: Decimal = self._dao.service_fees
        self.business_identifier: str = self._dao.business_identifier
        self.dat_number: str = self._dao.dat_number
        self.cfs_account_id: int = self._dao.cfs_account_id
        self.details: dict = self._dao.details
        self.gst: Decimal = self._dao.gst

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
    def payment_method_code(self):
        """Return the payment_method_code."""
        return self._payment_method_code

    @payment_method_code.setter
    def payment_method_code(self, value: str):
        """Set the payment_method_code."""
        self._payment_method_code = value
        self._dao.payment_method_code = value

    @property
    def invoice_status_code(self):
        """Return the invoice_status_code."""
        return self._invoice_status_code

    @invoice_status_code.setter
    def invoice_status_code(self, value: str):
        """Set the invoice_status_code."""
        self._invoice_status_code = value
        self._dao.invoice_status_code = value

    @property
    def payment_account_id(self):
        """Return the payment_account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: str):
        """Set the payment_account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def bcol_account(self):
        """Return the bcol_account."""
        return self._bcol_account

    @bcol_account.setter
    def bcol_account(self, value: str):
        """Set the bcol_account."""
        self._bcol_account = value
        self._dao.bcol_account = value

    @property
    def refund(self):
        """Return the refund."""
        return self._refund

    @refund.setter
    def refund(self, value: Decimal):
        """Set the refund."""
        self._refund = value
        self._dao.refund = value

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
    def refund_date(self):
        """Return the refund_date."""
        return self._refund_date

    @refund_date.setter
    def refund_date(self, value: datetime):
        """Set the refund_date."""
        self._refund_date = value
        self._dao.refund_date = value

    @property
    def total(self):
        """Return the total."""
        return self._total

    @total.setter
    def total(self, value: Decimal):
        """Set the fee_start_date."""
        self._total = value
        self._dao.total = value

    @property
    def paid(self):
        """Return the paid."""
        return self._paid

    @paid.setter
    def paid(self, value: Decimal):
        """Set the paid."""
        self._paid = value
        self._dao.paid = value

    @property
    def payment_line_items(self):
        """Return the payment payment_line_items."""
        return self._payment_line_items

    @payment_line_items.setter
    def payment_line_items(self, value):
        """Set the payment_line_items."""
        self._payment_line_items = value
        self._dao.payment_line_items = value

    @property
    def corp_type_code(self):
        """Return the corp_type_code."""
        return self._corp_type_code

    @corp_type_code.setter
    def corp_type_code(self, value):
        """Set the corp_type_code."""
        self._corp_type_code = value
        self._dao.corp_type_code = value

    @property
    def receipts(self):
        """Return the receipts."""
        return self._receipts

    @receipts.setter
    def receipts(self, value):
        """Set the receipts."""
        self._receipts = value
        self._dao.receipts = value

    @property
    def routing_slip(self):
        """Return the routing_slip."""
        return self._routing_slip

    @routing_slip.setter
    def routing_slip(self, value: str):
        """Set the routing_slip."""
        self._routing_slip = value
        self._dao.routing_slip = value

    @property
    def filing_id(self):
        """Return the filing_id."""
        return self._filing_id

    @filing_id.setter
    def filing_id(self, value: str):
        """Set the filing_id."""
        self._filing_id = value
        self._dao.filing_id = value

    @property
    def folio_number(self):
        """Return the folio_number."""
        return self._folio_number

    @folio_number.setter
    def folio_number(self, value: str):
        """Set the folio_number."""
        self._folio_number = value
        self._dao.folio_number = value

    @property
    def service_fees(self):
        """Return the service_fees."""
        return self._service_fees

    @service_fees.setter
    def service_fees(self, value: Decimal):
        """Set the service_fees."""
        self._service_fees = value
        self._dao.service_fees = value

    @property
    def business_identifier(self):
        """Return the business_identifier."""
        return self._business_identifier

    @business_identifier.setter
    def business_identifier(self, value: int):
        """Set the business_identifier."""
        self._business_identifier = value
        self._dao.business_identifier = value

    @property
    def dat_number(self):
        """Return the dat_number."""
        return self._dat_number

    @dat_number.setter
    def dat_number(self, value: str):
        """Set the dat_number."""
        self._dat_number = value
        self._dao.dat_number = value

    @property
    def cfs_account_id(self):
        """Return the cfs_account_id."""
        return self._cfs_account_id

    @cfs_account_id.setter
    def cfs_account_id(self, value: int):
        """Set the cfs_account_id."""
        self._cfs_account_id = value
        self._dao.cfs_account_id = value

    @property
    def details(self):
        """Return the details."""
        return self._details

    @details.setter
    def details(self, value: str):
        """Set the details."""
        self._details = value
        self._dao.details = value

    @property
    def created_on(self):
        """Return the created date."""
        return self._dao.created_on

    @created_on.setter
    def created_on(self, value: datetime):
        """Set the created date."""
        self._dao.created_on = value

    @property
    def gst(self):
        """Return the gst."""
        return self._gst

    @gst.setter
    def gst(self, value: Decimal):
        """Set the gst."""
        self._gst = value
        self._dao.gst = value

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

    def asdict(self, include_dynamic_fields: bool = False, include_links: bool = True):
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
        d = invoice_schema.dump(self._dao)
        self._add_dynamic_fields(d, include_dynamic_fields)
        return d

    @staticmethod
    def populate(value):
        """Populate invoice service."""
        invoice: Invoice = Invoice()
        invoice._dao = value  # pylint: disable=protected-access
        return invoice

    @staticmethod
    def find_by_id(identifier: int, skip_auth_check: bool = False, one_of_roles=ALL_ALLOWED_ROLES):
        """Find invoice by id."""
        invoice_dao = InvoiceModel.find_by_id(identifier)

        if not invoice_dao:
            raise BusinessException(Error.INVALID_INVOICE_ID)

        if not skip_auth_check:
            Invoice._check_for_auth(invoice_dao, one_of_roles)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug(">find_by_id")
        return invoice

    @staticmethod
    @user_context
    def find_composite_by_id(identifier: int, **kwargs):
        """Find the invoice composite by id."""
        user: UserContext = kwargs["user"]
        invoice_composite = InvoiceCompositeModel.find_by_id(identifier)

        if not invoice_composite:
            raise BusinessException(Error.INVALID_INVOICE_ID)

        if not user.has_role(Role.VIEW_ALL_TRANSACTIONS.value):
            products, filter_by_product = ProductAuthUtil.check_products_from_role_pattern(
                role_pattern=RolePattern.PRODUCT_VIEW_TRANSACTION.value,
                all_products_role=Role.VIEW_ALL_TRANSACTIONS.value,
            )
            if invoice_composite.corp_type.product not in products:
                abort(403)

        current_app.logger.debug(">find_composite_by_id")
        return InvoiceCompositeModel.dao_to_dict(invoice_composite)

    @staticmethod
    def find_invoices_for_payment(
        payment_id: int, reference_status=InvoiceReferenceStatus.ACTIVE.value
    ) -> list[Invoice]:
        """Find invoices by payment id."""
        invoices: list[Invoice] = []
        invoice_daos: list[InvoiceModel] = InvoiceModel.find_invoices_for_payment(payment_id, reference_status)

        for invoice_dao in invoice_daos:
            invoice = Invoice()
            invoice._dao = invoice_dao  # pylint: disable=protected-access
            invoices.append(invoice)

        current_app.logger.debug(">find_invoices_for_payment")
        return invoices

    @staticmethod
    def find_invoices(business_identifier: str) -> dict[str, any]:
        """Find invoices by business identifier."""
        invoices: dict[str, any] = {"invoices": []}
        invoice_daos: list[InvoiceModel] = InvoiceModel.find_by_business_identifier(business_identifier)

        for invoice_dao in invoice_daos:
            invoice = Invoice()
            invoice._dao = invoice_dao  # pylint: disable=protected-access
            invoices["invoices"].append(invoice.asdict())

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

        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(invoice_dao.payment_account_id)
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
    def _check_for_auth(dao, one_of_roles=ALL_ALLOWED_ROLES):
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

    @staticmethod
    def get_invoices_and_payment_accounts_for_statements(search_filter: dict):
        """Slimmed down version for statements."""
        auth_account_ids = select(func.unnest(cast(search_filter.get("authAccountIds", []), ARRAY(TEXT))))
        query = (
            db.session.query(InvoiceModel)
            .join(PaymentAccountModel, InvoiceModel.payment_account_id == PaymentAccountModel.id)
            .filter(PaymentAccountModel.auth_account_id.in_(auth_account_ids))
        )
        # If an account is within these payment methods - limit invoices to these payment methods.
        # Used for transitioning payment method and an interim statement is created (There could be different payment
        # methods for the transition day and we don't want it on both statements)
        if search_filter.get("matchPaymentMethods", None):
            query = query.filter(
                or_(
                    and_(
                        PaymentAccountModel.payment_method == PaymentMethod.EFT.value,
                        InvoiceModel.payment_method_code == PaymentAccountModel.payment_method,
                    ),
                    and_(
                        PaymentAccountModel.payment_method != PaymentMethod.EFT.value,
                        InvoiceModel.payment_method_code != PaymentMethod.EFT.value,
                    ),
                )
            )

        query = Invoice.filter_date(query, search_filter).with_entities(
            InvoiceModel.id,
            InvoiceModel.payment_method_code,
            PaymentAccountModel.auth_account_id,
            PaymentAccountModel.id.label("payment_account_id"),
        )
        return query.all()

    @classmethod
    def filter_date(cls, query, search_filter: dict):
        """Filter by date."""
        # Find start and end dates
        created_from: datetime = None
        created_to: datetime = None
        if get_str_by_path(search_filter, "dateFilter/startDate"):
            created_from = datetime.strptime(get_str_by_path(search_filter, "dateFilter/startDate"), DT_SHORT_FORMAT)
        if get_str_by_path(search_filter, "dateFilter/endDate"):
            created_to = datetime.strptime(get_str_by_path(search_filter, "dateFilter/endDate"), DT_SHORT_FORMAT)
        if get_str_by_path(search_filter, "weekFilter/index"):
            created_from, created_to = get_week_start_and_end_date(
                index=int(get_str_by_path(search_filter, "weekFilter/index"))
            )
        if get_str_by_path(search_filter, "monthFilter/month") and get_str_by_path(search_filter, "monthFilter/year"):
            month = int(get_str_by_path(search_filter, "monthFilter/month"))
            year = int(get_str_by_path(search_filter, "monthFilter/year"))
            created_from, created_to = get_first_and_last_dates_of_month(month=month, year=year)

        if created_from and created_to:
            # Truncate time for from date and add max time for to date
            tz_name = current_app.config["LEGISLATIVE_TIMEZONE"]
            tz_local = pytz.timezone(tz_name)

            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz_local)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(tz_local)
            query = query.filter(
                func.timezone(tz_name, func.timezone("UTC", InvoiceModel.created_on)).between(created_from, created_to)
            )
        return query
