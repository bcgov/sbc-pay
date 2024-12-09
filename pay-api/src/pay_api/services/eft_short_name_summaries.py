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
"""Service to provide summarized information for EFT Short names."""
from __future__ import annotations

from flask import current_app
from sqlalchemy import and_, func, or_

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTShortnameSummarySchema as EFTSummarySchema
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import db
from pay_api.models.eft_refund import EFTRefund as EFTRefundModel
from pay_api.utils.enums import EFTFileLineType, EFTProcessStatus, EFTShortnameRefundStatus, EFTShortnameStatus
from pay_api.utils.util import unstructure_schema_items

from .eft_short_names import EFTShortnamesSearch


class EFTShortnameSummaries:
    """Service to provide summarized information for EFT Short names."""

    @classmethod
    def search(cls, search_criteria: EFTShortnamesSearch):
        """Search eft short name summaries."""
        current_app.logger.debug("<search")
        search_count = cls.get_search_count()
        search_query = cls.get_search_query(search_criteria)
        pagination = search_query.paginate(per_page=search_criteria.limit, page=search_criteria.page)

        summary_list = unstructure_schema_items(EFTSummarySchema, pagination.items)

        current_app.logger.debug(">search")
        return {
            "state_total": search_count,
            "page": search_criteria.page,
            "limit": search_criteria.limit,
            "items": summary_list,
            "total": pagination.total,
        }

    @staticmethod
    def get_last_payment_received_query():
        """Query for EFT most recent transaction deposit date."""
        return (
            db.session.query(
                EFTTransactionModel.deposit_date,
                EFTTransactionModel.short_name_id,
                func.row_number()
                .over(
                    partition_by=EFTTransactionModel.short_name_id,
                    order_by=[
                        EFTTransactionModel.deposit_date.desc(),
                        EFTTransactionModel.id,
                    ],
                )
                .label("rn"),
            )
            .filter(
                and_(
                    EFTTransactionModel.short_name_id.isnot(None),
                    EFTTransactionModel.status_code == EFTProcessStatus.COMPLETED.value,
                )
            )
            .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
        )

    @staticmethod
    def get_linked_count_query():
        """Query for EFT linked account count."""
        # pylint: disable=not-callable
        return (
            db.session.query(
                EFTShortnameLinksModel.eft_short_name_id,
                func.count(EFTShortnameLinksModel.eft_short_name_id).label("count"),
            )
            .filter(
                EFTShortnameLinksModel.status_code.in_(
                    [EFTShortnameStatus.PENDING.value, EFTShortnameStatus.LINKED.value]
                )
            )
            .group_by(EFTShortnameLinksModel.eft_short_name_id)
        )

    @staticmethod
    def get_shortname_refund_query():
        """Query for EFT shortname refund."""
        return (
            db.session.query(EFTRefundModel.short_name_id, EFTRefundModel.status)
            .filter(EFTRefundModel.status.in_([EFTShortnameRefundStatus.PENDING_APPROVAL.value]))
            .distinct(EFTRefundModel.short_name_id)
        )

    @staticmethod
    def get_remaining_credit_query():
        """Query for EFT remaining credit amount."""
        return db.session.query(
            EFTCreditModel.short_name_id,
            (func.coalesce(func.sum(EFTCreditModel.remaining_amount), 0)).label("total"),
        ).group_by(EFTCreditModel.short_name_id)

    @staticmethod
    def get_search_count():
        """Get a total count of short name summary results."""
        current_app.logger.debug("<get_search_count")

        count_query = (
            db.session.query(EFTShortnameModel.id).group_by(EFTShortnameModel.id).with_entities(EFTShortnameModel.id)
        )

        current_app.logger.debug(">get_search_count")
        return count_query.count()

    @classmethod
    def get_search_query(cls, search_criteria: EFTShortnamesSearch):
        """Query for short names based on search criteria."""
        linked_account_subquery = cls.get_linked_count_query().subquery()
        credit_remaining_subquery = cls.get_remaining_credit_query().subquery()
        last_payment_subquery = cls.get_last_payment_received_query().subquery()
        refund_shortname_subquery = cls.get_shortname_refund_query().subquery()

        query = (
            db.session.query(
                EFTShortnameModel.id,
                EFTShortnameModel.short_name,
                EFTShortnameModel.type,
                EFTShortnameModel.cas_supplier_number,
                EFTShortnameModel.cas_supplier_site,
                EFTShortnameModel.email,
                func.coalesce(linked_account_subquery.c.count, 0).label("linked_accounts_count"),
                func.coalesce(credit_remaining_subquery.c.total, 0).label("credits_remaining"),
                last_payment_subquery.c.deposit_date.label("last_payment_received_date"),
                refund_shortname_subquery.c.status.label("refund_status"),
            )
            .outerjoin(
                linked_account_subquery,
                linked_account_subquery.c.eft_short_name_id == EFTShortnameModel.id,
            )
            .outerjoin(
                credit_remaining_subquery,
                credit_remaining_subquery.c.short_name_id == EFTShortnameModel.id,
            )
            .outerjoin(
                last_payment_subquery,
                and_(
                    last_payment_subquery.c.short_name_id == EFTShortnameModel.id,
                    last_payment_subquery.c.rn == 1,
                ),
            )
        ).outerjoin(
            refund_shortname_subquery,
            refund_shortname_subquery.c.short_name_id == EFTShortnameModel.id,
        )

        query = query.filter_conditionally(search_criteria.id, EFTShortnameModel.id)
        query = query.filter_conditionally(search_criteria.short_name_type, EFTShortnameModel.type)
        query = query.filter_conditionally(search_criteria.short_name, EFTShortnameModel.short_name, is_like=True)
        query = query.filter_conditional_date_range(
            start_date=search_criteria.deposit_start_date,
            end_date=search_criteria.deposit_end_date,
            model_attribute=last_payment_subquery.c.deposit_date,
        )
        query = query.filter_conditionally(search_criteria.credit_remaining, credit_remaining_subquery.c.total)

        if search_criteria.linked_accounts_count == 0:
            query = query.filter(
                or_(
                    linked_account_subquery.c.count == 0,
                    linked_account_subquery.c.count.is_(None),
                )
            )
        else:
            query = query.filter_conditionally(search_criteria.linked_accounts_count, linked_account_subquery.c.count)

        query = query.order_by(last_payment_subquery.c.deposit_date.asc())
        return query
