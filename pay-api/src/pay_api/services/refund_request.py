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
"""Service to manage Receipt."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal  # noqa: TC003

from flask import current_app
from sqlalchemy import case, func

from pay_api.models import db
from pay_api.models.corp_type import CorpType as CorpTypeModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.refund import Refund as RefundModel
from pay_api.models.refund import RefundDTO
from pay_api.models.refunds_partial import RefundsPartial as RefundPartialModel
from pay_api.services import RefundService
from pay_api.utils.converter import Converter
from pay_api.utils.enums import RefundType
from pay_api.utils.user_context import UserContext, user_context


@dataclass
class RefundRequestsSearch:
    """Used for searching refund requests records."""

    refund_type: str | None = RefundType.INVOICE.value
    payment_method: str | None = None
    refund_reason: str | None = None
    refund_amount: Decimal | None = None
    refund_method: str | None = None
    requested_by: str | None = None
    requested_start_date: str | None = None
    requested_end_date: str | None = None
    status: str | None = None
    transaction_amount: Decimal | None = None
    filter_by_product: bool = False
    allowed_products: list[str] = None
    page: int | None = 1
    limit: int | None = 10


class RefundRequestService:
    """Service to manage refund requests."""

    @staticmethod
    @user_context
    def find_by_id(refund_id: int, filter_by_product: bool, products: list[str], **kwargs):
        """Find refund by refund id."""
        user: UserContext = kwargs["user"]
        refund = RefundModel.find_by_id(refund_id)
        invoice = InvoiceModel.find_by_id(refund.invoice_id)

        if filter_by_product:
            RefundService.validate_product_authorization(invoice, products, user.is_system())

        refund_partial_lines = RefundPartialModel.get_partial_refunds_by_refund_id(refund.id) or []
        normalized_refund_lines, refund_total = RefundService.normalize_partial_refund_lines(refund_partial_lines)
        if not refund_partial_lines:
            refund_total = invoice.total

        return Converter().unstructure(
            RefundDTO.from_row(
                refund, invoice.total, invoice.payment_method_code, normalized_refund_lines, refund_total
            )
        )

    @classmethod
    def get_status_search_count(cls, search_criteria: RefundRequestsSearch):
        """Get total count of results based on status search criteria."""
        current_app.logger.debug("<get_search_count")

        query = db.session.query(RefundModel)
        query = query.filter_conditionally(search_criteria.status, RefundModel.status)
        if search_criteria.filter_by_product:
            query = query.join(InvoiceModel, InvoiceModel.id == RefundModel.invoice_id)
            query = query.join(CorpTypeModel, CorpTypeModel.code == InvoiceModel.corp_type_code)
            query = query.filter(CorpTypeModel.product.in_(search_criteria.allowed_products))

        count_query = query.group_by(RefundModel.id).with_entities(RefundModel.id)

        current_app.logger.debug(">get_search_count")
        return count_query.count()

    @classmethod
    def get_partial_refund_sum_query(cls):
        """Get subquery for partial refund lines sum."""
        return db.session.query(
            RefundPartialModel.refund_id,
            (func.coalesce(func.sum(RefundPartialModel.refund_amount), 0)).label("refund_partial_total"),
        ).group_by(RefundPartialModel.refund_id)

    @classmethod
    def get_search_query(cls, search_criteria: RefundRequestsSearch):
        """Get results based on refund request search criteria."""
        current_app.logger.debug("<get_search_query")
        partial_refund_total_subquery = cls.get_partial_refund_sum_query().subquery()
        prt_subquery = partial_refund_total_subquery.c
        query = (
            db.session.query(
                RefundModel,
                InvoiceModel.total.label("transaction_amount"),
                InvoiceModel.payment_method_code.label("payment_method"),
                case(
                    (prt_subquery.refund_partial_total > 0, prt_subquery.refund_partial_total),
                    else_=InvoiceModel.total,
                ).label("refund_amount"),
            )
            .join(InvoiceModel, InvoiceModel.id == RefundModel.invoice_id)
            .join(CorpTypeModel, CorpTypeModel.code == InvoiceModel.corp_type_code)
            .outerjoin(
                partial_refund_total_subquery,
                partial_refund_total_subquery.c.refund_id == RefundModel.id,
            )
        )
        query = query.filter_conditionally(search_criteria.refund_type, RefundModel.type)
        query = query.filter_conditionally(search_criteria.status, RefundModel.status)
        query = query.filter_conditionally(search_criteria.requested_by, RefundModel.requested_by, is_like=True)
        query = query.filter_conditionally(search_criteria.refund_reason, RefundModel.reason, is_like=True)
        query = query.filter_conditionally(search_criteria.refund_method, RefundModel.refund_method)
        query = query.filter_conditionally(search_criteria.payment_method, InvoiceModel.payment_method_code)
        query = query.filter_conditionally(search_criteria.transaction_amount, InvoiceModel.total)
        query = query.filter_conditionally(search_criteria.refund_amount, prt_subquery.refund_partial_total)

        query = query.filter_conditional_date_range(
            start_date=search_criteria.requested_start_date,
            end_date=search_criteria.requested_end_date,
            model_attribute=RefundModel.requested_date,
            cast_to_date=False,
        )

        if search_criteria.filter_by_product:
            query = query.filter(CorpTypeModel.product.in_(search_criteria.allowed_products))

        current_app.logger.debug(">get_search_query")
        return query

    @classmethod
    def search(cls, search_criteria: RefundRequestsSearch):
        """Search refund requests."""
        current_app.logger.debug("<refund_requests search")
        status_count = cls.get_status_search_count(search_criteria)
        search_query = cls.get_search_query(search_criteria)
        pagination = search_query.paginate(per_page=search_criteria.limit, page=search_criteria.page)
        converter = Converter()
        refund_requests_list = []
        for refund, transaction_amount, payment_method, refund_amount in pagination.items:
            refund_partial_lines = RefundPartialModel.get_partial_refunds_by_refund_id(refund.id) or []
            normalized_refund_lines, _ = RefundService.normalize_partial_refund_lines(refund_partial_lines)
            refund_requests_list.append(
                converter.unstructure(
                    RefundDTO.from_row(
                        refund, transaction_amount, payment_method, normalized_refund_lines, refund_amount
                    )
                )
            )

        current_app.logger.debug(">refund requests search")
        return {
            "status_total": status_count,
            "page": search_criteria.page,
            "limit": search_criteria.limit,
            "items": refund_requests_list,
            "total": pagination.total,
        }
