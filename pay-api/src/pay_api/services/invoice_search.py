# Copyright © 2025 Province of British Columbia
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
"""Service to support invoice searches."""

from dateutil import parser
from flask import current_app
from sqlalchemy import String, and_, cast, exists, func, or_, select
from sqlalchemy.orm import contains_eager, joinedload, lazyload, load_only, with_expression

from pay_api.exceptions import BusinessException
from pay_api.models import (
    AppliedCredits,
    CorpType,
    FeeSchedule,
    Invoice,
    InvoiceReference,
    InvoiceSearchModel,
    InvoiceStatusCode,
    PaymentAccount,
    PaymentLineItem,
    Refund,
    RefundsPartial,
    db,
)
from pay_api.models.payment import TransactionSearchParams
from pay_api.models.search.invoice_composite_model import InvoiceCompositeModel
from pay_api.services.code import Code as CodeService
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.services.oauth_service import OAuthService
from pay_api.services.payment import PaymentReportInput
from pay_api.services.payment_calculations import (
    build_grouped_invoice_context,
    build_statement_context,
    build_statement_summary_context,
)
from pay_api.utils.converter import Converter
from pay_api.utils.dataclasses import PurchaseHistorySearch
from pay_api.utils.enums import AuthHeaderType, Code, ContentType, InvoiceStatus, PaymentMethod, RefundStatus
from pay_api.utils.errors import Error
from pay_api.utils.sqlalchemy import JSONPath
from pay_api.utils.user_context import user_context
from pay_api.utils.util import get_local_formatted_date, get_statement_currency_string

from .report_service import ReportRequest, ReportService


class InvoiceSearch:
    """Service to support invoice searches."""

    @classmethod
    def generate_base_transaction_query(cls, include_credits_and_partial_refunds: bool):
        """Generate a base query."""
        options = [
            lazyload("*"),
            load_only(
                InvoiceCompositeModel.id,
                InvoiceCompositeModel.corp_type_code,
                InvoiceCompositeModel.created_on,
                InvoiceCompositeModel.payment_date,
                InvoiceCompositeModel.refund_date,
                InvoiceCompositeModel.invoice_status_code,
                InvoiceCompositeModel.total,
                InvoiceCompositeModel.gst,
                InvoiceCompositeModel.service_fees,
                InvoiceCompositeModel.paid,
                InvoiceCompositeModel.refund,
                InvoiceCompositeModel.folio_number,
                InvoiceCompositeModel.created_name,
                InvoiceCompositeModel.invoice_status_code,
                InvoiceCompositeModel.payment_method_code,
                InvoiceCompositeModel.details,
                InvoiceCompositeModel.business_identifier,
                InvoiceCompositeModel.created_by,
                InvoiceCompositeModel.filing_id,
                InvoiceCompositeModel.bcol_account,
                InvoiceCompositeModel.disbursement_date,
                InvoiceCompositeModel.disbursement_reversal_date,
                InvoiceCompositeModel.overdue_date,
            ),
            contains_eager(InvoiceCompositeModel.payment_line_items)
            .load_only(
                PaymentLineItem.description,
                PaymentLineItem.statutory_fees_gst,
                PaymentLineItem.service_fees_gst,
                PaymentLineItem.pst,
                PaymentLineItem.service_fees,
                PaymentLineItem.total,
            )
            .contains_eager(PaymentLineItem.fee_schedule)
            .load_only(FeeSchedule.filing_type_code),
            contains_eager(InvoiceCompositeModel.payment_account).load_only(
                PaymentAccount.auth_account_id,
                PaymentAccount.name,
                PaymentAccount.billable,
                PaymentAccount.branch_name,
            ),
            contains_eager(InvoiceCompositeModel.references).load_only(
                InvoiceReference.invoice_number,
                InvoiceReference.reference_number,
                InvoiceReference.status_code,
            ),
            with_expression(InvoiceCompositeModel.latest_refund_id, InvoiceCompositeModel.latest_refund_id_expr),
            with_expression(
                InvoiceCompositeModel.latest_refund_status, InvoiceCompositeModel.latest_refund_status_expr
            ),
            with_expression(InvoiceCompositeModel.full_refundable, InvoiceCompositeModel.full_refundable_expr),
            with_expression(InvoiceCompositeModel.partial_refundable, InvoiceCompositeModel.partial_refundable_expr),
        ]

        if include_credits_and_partial_refunds:
            options.extend(
                [
                    joinedload(InvoiceCompositeModel.applied_credits),
                    joinedload(
                        InvoiceCompositeModel.partial_refunds.and_(
                            exists().where(
                                and_(
                                    Refund.id == RefundsPartial.refund_id,
                                    Refund.status.in_(
                                        [
                                            RefundStatus.APPROVED.value,
                                            RefundStatus.PENDING_APPROVAL.value,
                                            RefundStatus.APPROVAL_NOT_REQUIRED.value,
                                        ]
                                    ),
                                )
                            )
                        )
                    ),
                ]
            )

        return (
            db.session.query(InvoiceCompositeModel)
            .join(PaymentAccount, Invoice.payment_account_id == PaymentAccount.id)
            .join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .join(
                FeeSchedule,
                FeeSchedule.fee_schedule_id == PaymentLineItem.fee_schedule_id,
            )
            .outerjoin(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .options(*options)
        )

    @classmethod
    def generate_subquery(cls, params: TransactionSearchParams):
        """Generate subquery for invoices, used for pagination."""
        subquery = db.session.query(Invoice.id)
        subquery = (
            cls.filter(subquery, params.auth_account_id, params.search_filter, include_joins=True)
            .distinct()
            .order_by(Invoice.id.desc())
        )
        if params.limit:
            subquery = subquery.limit(params.limit)
        if params.limit and params.page:
            if params.no_counts:
                params.limit -= 1
            subquery = subquery.offset((params.page - 1) * params.limit)
        return subquery

    @classmethod
    def filter(cls, query, auth_account_id: str, search_filter: dict, include_joins=False):
        """For filtering queries."""
        query = cls.filter_payment_account(query, auth_account_id, search_filter, include_joins)
        if status_code := search_filter.get("statusCode", None):
            query = cls._apply_status_filter(query, status_code)

        # Handle deprecated status filtering
        if status := search_filter.get("status", None):
            query = cls._apply_status_filter(query, status)
        if search_filter.get("folioNumber", None):
            query = query.filter(Invoice.folio_number == search_filter.get("folioNumber"))
        if business_identifier := search_filter.get("businessIdentifier", None):
            query = query.filter(Invoice.business_identifier.ilike(f"%{business_identifier}%"))
        if created_by := search_filter.get("createdBy", None):  # pylint: disable=no-member
            # depreciating (replacing with createdName)
            query = query.filter(Invoice.created_name.ilike(f"%{created_by}%"))  # pylint: disable=no-member
        if created_name := search_filter.get("createdName", None):
            query = query.filter(Invoice.created_name.ilike(f"%{created_name}%"))  # pylint: disable=no-member
        if invoice_id := search_filter.get("id", None):
            query = query.filter(cast(Invoice.id, String).like(f"%{invoice_id}%"))
        if invoice_number := search_filter.get("invoiceNumber", None):
            if include_joins:
                query = query.join(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            query = query.filter(InvoiceReference.invoice_number.ilike(f"%{invoice_number}%"))

        query = cls.filter_corp_type(query, search_filter)
        query = cls.filter_payment(query, search_filter)
        query = cls.filter_details(query, search_filter, include_joins)
        query = InvoiceService.filter_date(query, search_filter)
        return query

    @classmethod
    def _apply_status_filter(cls, query, status_code: str):
        """Apply status filter to query."""
        if status_code == InvoiceStatus.PARTIALLY_CREDITED.value:
            return query.filter(
                exists().where(and_(RefundsPartial.invoice_id == Invoice.id, RefundsPartial.is_credit.is_(True)))
            )
        elif status_code == InvoiceStatus.PARTIALLY_REFUNDED.value:
            return query.filter(
                exists().where(and_(RefundsPartial.invoice_id == Invoice.id, RefundsPartial.is_credit.is_(False)))
            )
        else:
            return query.filter(Invoice.invoice_status_code == status_code)

    @classmethod
    def _apply_payment_method_filter(cls, query, payment_type: str):
        """Apply payment method filter to query."""
        if payment_type == "NO_FEE":
            return query.filter(Invoice.total == 0)
        elif payment_type == PaymentMethod.CREDIT.value:
            return query.filter(exists().where(AppliedCredits.invoice_id == Invoice.id))
        elif payment_type in [PaymentMethod.PAD.value, PaymentMethod.ONLINE_BANKING.value]:
            # For PAD and ONLINE_BANKING, exclude invoices where sum of AppliedCredits equals invoice total
            credit_total_subquery = (
                select(AppliedCredits.invoice_id, func.sum(AppliedCredits.amount_applied).label("total_applied"))
                .group_by(AppliedCredits.invoice_id)
                .subquery()
            )

            return query.outerjoin(credit_total_subquery, credit_total_subquery.c.invoice_id == Invoice.id).filter(
                and_(
                    Invoice.total != 0,
                    Invoice.payment_method_code == payment_type,
                    or_(
                        credit_total_subquery.c.total_applied.is_(None),
                        credit_total_subquery.c.total_applied != Invoice.total,
                    ),
                )
            )
        else:
            return query.filter(Invoice.total != 0).filter(Invoice.payment_method_code == payment_type)

    @classmethod
    def filter_payment_account(cls, query, auth_account_id, search_filter: dict, include_joins=False):
        """Use subquery to look for payment accounts ahead of time, much faster and easier."""
        account_name = search_filter.get("accountName", None)
        if auth_account_id:
            payment_account_id = (
                db.session.query(PaymentAccount.id).filter(PaymentAccount.auth_account_id == auth_account_id).scalar()
            )
            query = query.filter(Invoice.payment_account_id == (payment_account_id or -1))
        if account_name:
            if include_joins:
                query = query.join(PaymentAccount, PaymentAccount.id == Invoice.payment_account_id)
            query = query.filter(PaymentAccount.name.ilike(f"%{account_name}%"))
        return query

    @classmethod
    def filter_corp_type(cls, query, search_filter: dict):
        """Filter for corp type."""
        if product := search_filter.get("userProductCode", None):
            # Product claim - We should restrict filter to this if provided
            query = query.join(CorpType, CorpType.code == Invoice.corp_type_code).filter(CorpType.product == product)
        elif products := search_filter.get("allowed_products", None):
            # products list is based on security roles, if a product filter is specified needs to exist on the list
            single_product = search_filter.get("product", None)
            if single_product and single_product in products:
                products = [single_product]

            query = query.join(CorpType, CorpType.code == Invoice.corp_type_code).filter(CorpType.product.in_(products))
        elif product := search_filter.get("product", None):
            query = query.join(CorpType, CorpType.code == Invoice.corp_type_code).filter(CorpType.product == product)

        return query

    @classmethod
    def filter_payment(cls, query, search_filter: dict):
        """Filter for payment."""
        if payment_type := search_filter.get("paymentMethod", None):
            query = cls._apply_payment_method_filter(query, payment_type)
        return query

    @classmethod
    def filter_details(cls, query, search_filter: dict, include_joins=False):
        """Filter by details."""
        line_item = search_filter.get("lineItems", None)
        line_item_or_details = search_filter.get("lineItemsAndDetails", None)
        if (line_item or line_item_or_details) and include_joins:
            query = query.join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
        if line_item:
            query = query.filter(PaymentLineItem.description.ilike(f"%{line_item}%"))
        if details := search_filter.get("details", None):
            query = query.filter(
                or_(
                    func.jsonb_path_exists(
                        Invoice.details, cast(f'$[*] ? (@.value like_regex "(?i).*{details}.*")', JSONPath())
                    ),
                    func.jsonb_path_exists(
                        Invoice.details, cast(f'$[*] ? (@.label like_regex "(?i).*{details}.*")', JSONPath())
                    ),
                )
            )
        if line_item_or_details:
            query = query.filter(
                or_(
                    PaymentLineItem.description.ilike(f"%{line_item_or_details}%"),
                    func.jsonb_path_exists(
                        Invoice.details,
                        cast(f'$[*] ? (@.value like_regex "(?i).*{line_item_or_details}.*")', JSONPath()),
                    ),
                    func.jsonb_path_exists(
                        Invoice.details,
                        cast(f'$[*] ? (@.label like_regex "(?i).*{line_item_or_details}.*")', JSONPath()),
                    ),
                )
            )

        return query

    @classmethod
    def get_count(cls, auth_account_id: str, search_filter: dict):
        """Slimmed downed version for count (less joins)."""
        query = db.session.query(func.distinct(Invoice.id))
        query = cls.filter(query, auth_account_id, search_filter, include_joins=True)
        count = query.count()
        return count

    @classmethod
    def search_without_counts(cls, params: TransactionSearchParams):
        """Search without using counts, ideally this will become our baseline."""
        query = cls.generate_base_transaction_query(include_credits_and_partial_refunds=True)
        query = cls.filter(query, params.auth_account_id, params.search_filter)
        # Grab +1, so we can check if there are more records.
        params.limit += 1
        sub_query = cls.generate_subquery(params).subquery()
        results = query.filter(Invoice.id.in_(sub_query.select())).order_by(Invoice.id.desc()).all()
        has_more = len(results) > params.limit
        return results[: params.limit], has_more

    @classmethod
    def search(  # noqa:E501; too-many-locals, too-many-branches, too-many-statements;
        cls, search_params: PurchaseHistorySearch
    ):
        """Search for purchase history."""
        executor = current_app.extensions["flask_executor"]
        search_filter = search_params.search_filter
        query = cls.generate_base_transaction_query(include_credits_and_partial_refunds=False)
        query = cls.filter(query, search_params.auth_account_id, search_filter)
        if not search_params.return_all:
            count_future = executor.submit(cls.get_count, search_params.auth_account_id, search_filter)
            sub_query = cls.generate_subquery(
                TransactionSearchParams(
                    auth_account_id=search_params.auth_account_id,
                    search_filter=search_filter,
                    page=search_params.page,
                    limit=search_params.limit,
                )
            )
            query = query.filter(Invoice.id.in_(sub_query.subquery().select())).order_by(Invoice.id.desc())
            result_future = executor.submit(query.all)
            count = count_future.result()
            result = result_future.result()
            # If maximum number of records is provided, return it as total
            if search_params.max_no_records > 0:
                count = search_params.max_no_records if search_params.max_no_records < count else count
        elif search_params.max_no_records > 0:
            # If maximum number of records is provided, set the page with that number
            sub_query = cls.generate_subquery(
                TransactionSearchParams(
                    auth_account_id=search_params.auth_account_id,
                    search_filter=search_filter,
                    limit=search_params.max_no_records,
                    page=None,
                )
            )
            query, count = (
                query.filter(Invoice.id.in_(sub_query.subquery().select())),
                sub_query.count(),
            )
            if search_params.query_only:
                return query, count
            else:
                return query.all(), count
        else:
            count = cls.get_count(search_params.auth_account_id, search_filter)
            if count > 100000:
                raise BusinessException(Error.PAYMENT_SEARCH_TOO_MANY_RECORDS)
            if search_params.query_only:
                return query, count
            result = query.all()
        return result, count

    @classmethod
    @user_context
    def search_purchase_history(cls, search_params: PurchaseHistorySearch, **kwargs):  # pylint: disable=too-many-locals
        """Search purchase history for the account."""
        current_app.logger.debug(f"<search_purchase_history {search_params.auth_account_id}")
        search_filter = search_params.search_filter
        search_params.max_no_records = (
            current_app.config.get("TRANSACTION_REPORT_DEFAULT_TOTAL", 0)
            if not search_filter or not any(search_filter.values())
            else 0
        )
        search_filter["allowed_products"] = search_params.allowed_products if search_params.filter_by_product else None
        search_filter["userProductCode"] = kwargs["user"].product_code
        data = {"page": search_params.page, "limit": search_params.limit, "items": []}
        if bool(search_filter.get("excludeCounts")):
            # Ideally our data tables will be using this call from now on much better performance.
            purchases, data["hasMore"] = cls.search_without_counts(
                TransactionSearchParams(
                    auth_account_id=search_params.auth_account_id,
                    search_filter=search_filter,
                    page=search_params.page,
                    limit=search_params.limit,
                    no_counts=True,
                )
            )
        else:
            # This is to maintain backwards compat for CSO, also for other functions like exporting to CSV etc.
            purchases, data["total"] = cls.search(search_params)
            if search_params.query_only:
                return purchases
        data = cls.create_payment_report_details(purchases, data)
        current_app.logger.debug(">search_purchase_history")
        return data

    @classmethod
    def create_payment_report_details(cls, purchases: tuple, data: dict) -> dict:  # pylint:disable=too-many-locals
        """Return payment report details by fetching the line items.

        purchases is tuple of payment and invoice model records.
        """
        if data is None or "items" not in data:
            data = {"items": []}

        invoice_search_list = [InvoiceSearchModel.from_row(invoice_dao) for invoice_dao in purchases]

        converter = Converter()
        invoice_list = converter.unstructure(invoice_search_list)
        data["items"] = [Converter.remove_nones(invoice_dict) for invoice_dict in invoice_list]
        return data

    @staticmethod
    def search_all_purchase_history(auth_account_id: str, search_filter: dict, content_type: str):
        """Return all results for the purchase history."""
        return InvoiceSearch.search_purchase_history(
            PurchaseHistorySearch(
                auth_account_id=auth_account_id,
                search_filter=search_filter,
                page=0,
                limit=0,
                return_all=True,
                query_only=content_type == ContentType.CSV.value,
            )
        )

    @staticmethod
    def create_payment_report(auth_account_id: str, search_filter: dict, content_type: str, report_name: str):
        """Create payment report."""
        current_app.logger.debug(f"<create_payment_report {auth_account_id}")

        results = InvoiceSearch.search_all_purchase_history(auth_account_id, search_filter, content_type)

        report_response = InvoiceSearch.generate_payment_report(
            PaymentReportInput(
                content_type=content_type,
                report_name=report_name,
                template_name="payment_transactions",
                results=results,
            )
        )
        current_app.logger.debug(">create_payment_report")

        return report_response

    @staticmethod
    def get_invoices_totals(invoices: dict, statement: dict) -> dict:
        """Tally up totals for a list of invoices."""
        totals = {
            "statutoryFees": 0,
            "serviceFees": 0,
            "fees": 0,
            "paid": 0,
            "due": 0,
        }

        for invoice in invoices:
            invoice["created_on"] = get_local_formatted_date(parser.parse(invoice["created_on"]))
            total = invoice.get("total", 0)
            service_fees = invoice.get("service_fees", 0)
            paid = invoice.get("paid", 0)
            refund = invoice.get("refund", 0)
            payment_method = invoice.get("payment_method")
            payment_date = invoice.get("payment_date")
            refund_date = invoice.get("refund_date")

            totals["fees"] += total
            totals["statutoryFees"] += total - service_fees
            totals["serviceFees"] += service_fees
            totals["due"] += total
            if not statement or payment_method != PaymentMethod.EFT.value:
                totals["due"] -= paid
                totals["paid"] += paid
                if paid == 0 and refund > 0:
                    totals["due"] -= refund
            elif payment_method == PaymentMethod.EFT.value:
                if payment_date and parser.parse(payment_date) <= parser.parse(statement.get("to_date", "")):
                    totals["due"] -= paid
                    totals["paid"] += paid
                # Scenario where payment was refunded, paid $0, refund = invoice total
                if (
                    paid == 0
                    and refund > 0
                    and refund_date
                    and parser.parse(refund_date) <= parser.parse(statement.get("to_date", ""))
                ):
                    totals["due"] -= refund

        return totals

    @staticmethod
    @user_context
    def generate_payment_report(report_inputs: PaymentReportInput, **kwargs):  # pylint: disable=too-many-locals
        """Prepare data and generate payment report by calling report api."""
        content_type = report_inputs.content_type
        results = report_inputs.results
        report_name = report_inputs.report_name
        template_name = report_inputs.template_name

        if content_type == ContentType.CSV.value:
            template_vars = InvoiceSearch._prepare_csv_data(results)
        else:
            # Use the status_code_description instead of status_code.
            # Future: move this into something more specialized.
            invoice_status_codes = CodeService.find_code_values_by_type(Code.INVOICE_STATUS.value)
            for invoice in results.get("items", None):
                filtered_codes = [cd for cd in invoice_status_codes["codes"] if cd["code"] == invoice["status_code"]]
                if filtered_codes:
                    invoice["status_code"] = filtered_codes[0]["description"]
            invoices = results.get("items", None)
            statement = kwargs.get("statement", {})
            totals = InvoiceSearch.get_invoices_totals(invoices, statement)

            account_info = None
            if kwargs.get("auth", None):
                account_id = kwargs.get("auth")["account"]["id"]
                contact_url = current_app.config.get("AUTH_API_ENDPOINT") + f"orgs/{account_id}/contacts"
                contact = OAuthService.get(
                    endpoint=contact_url,
                    token=kwargs["user"].bearer_token,
                    auth_header_type=AuthHeaderType.BEARER,
                    content_type=ContentType.JSON,
                ).json()

                account_info = kwargs.get("auth").get("account")
                account_info["contact"] = contact["contacts"][0]  # Get the first one from the list

            invoices = results.get("items", [])
            statement_summary = report_inputs.statement_summary
            grouped_invoices: list[dict] = build_grouped_invoice_context(invoices, statement, statement_summary)

            has_payment_instructions = any(item.get("payment_method") == "EFT" for item in grouped_invoices)

            formatted_totals = {}
            for key, value in totals.items():
                formatted_totals[key] = get_statement_currency_string(value)

            template_vars = {
                "statementSummary": build_statement_summary_context(statement_summary),
                "groupedInvoices": grouped_invoices,
                "total": formatted_totals,
                "account": account_info,
                "statement": build_statement_context(kwargs.get("statement")),
            }

            if has_payment_instructions:
                template_vars["hasPaymentInstructions"] = True

        report_response = ReportService.get_report_response(
            ReportRequest(
                report_name=report_name,
                template_name=template_name,
                template_vars=template_vars,
                populate_page_number=True,
                content_type=content_type,
                stream=True,
            )
        )
        return report_response

    @staticmethod
    def _prepare_csv_data(results_query):
        """Prepare data for creating a CSV report."""
        labels = [
            "Product",
            "Corp Type",
            "Transaction Type",
            "Transaction",
            "Transaction Details",
            "Folio Number",
            "Initiated By",
            "Date",
            "Purchase Amount",
            "GST",
            "Statutory Fee",
            "BCOL Fee",
            "Status",
            "Corp Number",
            "Transaction ID",
            "Invoice Reference Number",
        ]

        formatted_date = func.to_char(
            func.timezone("America/Los_Angeles", Invoice.created_on), "YYYY-MM-DD HH12:MI:SS AM"
        ).op("||")(" Pacific Time")

        # We need this because there are a wackload of filters that can be applied to the query.
        invoice_subq = results_query.with_entities(Invoice.id).distinct().subquery()

        query = (
            db.session.query(Invoice)
            .join(invoice_subq, invoice_subq.c.id == Invoice.id)
            .join(CorpType, CorpType.code == Invoice.corp_type_code)
            .join(InvoiceStatusCode, InvoiceStatusCode.code == Invoice.invoice_status_code)
            .outerjoin(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .outerjoin(FeeSchedule, FeeSchedule.fee_schedule_id == PaymentLineItem.fee_schedule_id)
            .outerjoin(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .with_entities(
                CorpType.product,
                Invoice.corp_type_code,
                func.string_agg(FeeSchedule.filing_type_code, ",").label("filing_type_codes"),
                func.string_agg(PaymentLineItem.description, ",").label("descriptions"),
                cast(None, db.String).label("details_formatted"),
                Invoice.folio_number,
                Invoice.created_name,
                formatted_date.label("created_on_formatted"),
                cast(Invoice.total, db.Float),
                cast(
                    func.sum(PaymentLineItem.statutory_fees_gst + PaymentLineItem.service_fees_gst)
                    + func.sum(PaymentLineItem.pst),
                    db.Float,
                ).label("total_tax"),
                cast(Invoice.total - func.coalesce(Invoice.service_fees, 0), db.Float).label("statutory_fee"),
                cast(func.coalesce(Invoice.service_fees, 0), db.Float).label("service_fee"),
                InvoiceStatusCode.description.label("invoice_status_code"),
                Invoice.business_identifier,
                Invoice.id,
                func.string_agg(InvoiceReference.invoice_number, ",").label("invoice_number"),
            )
            .group_by(
                CorpType.product,
                Invoice.corp_type_code,
                Invoice.folio_number,
                Invoice.created_name,
                Invoice.created_on,
                Invoice.total,
                Invoice.service_fees,
                InvoiceStatusCode.description,
                Invoice.business_identifier,
                Invoice.id,
            )
            .order_by(Invoice.id.desc())
        )

        return {
            "columns": labels,
            "values": [list(row) for row in query.all()],
        }
