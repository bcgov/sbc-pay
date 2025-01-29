# Copyright © 2023 Province of British Columbia
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
"""Service to manage EFT short name model operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from _decimal import Decimal
from flask import current_app
from sqlalchemy import case, or_
from sqlalchemy.sql.expression import exists

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTShortnameSchema
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.utils.converter import Converter
from pay_api.utils.enums import EFTPaymentActions, EFTShortnameStatus, PaymentMethod
from pay_api.utils.errors import Error
from pay_api.utils.util import unstructure_schema_items

from ..utils.query_util import QueryUtils
from .eft_service import EftService
from .eft_statements import EFTStatements


@dataclass
class EFTShortnamesSearch:  # pylint: disable=too-many-instance-attributes
    """Used for searching EFT short name records."""

    id: Optional[int] = None
    account_id: Optional[str] = None
    account_id_list: Optional[List[str]] = None
    allow_partial_account_id: Optional[bool] = True
    account_name: Optional[str] = None
    account_branch: Optional[str] = None
    amount_owing: Optional[Decimal] = None
    deposit_start_date: Optional[date] = None
    deposit_end_date: Optional[date] = None
    credit_remaining: Optional[Decimal] = None
    linked_accounts_count: Optional[int] = None
    short_name: Optional[str] = None
    short_name_type: Optional[str] = None
    statement_id: Optional[int] = None
    state: Optional[List[str]] = None
    page: Optional[int] = 1
    limit: Optional[int] = 10


class EFTShortnames:  # pylint: disable=too-many-instance-attributes
    """Service to manage EFT short name model operations."""

    @classmethod
    def process_payment_action(cls, short_name_id: int, request: Dict):
        """Process EFT payment action."""
        current_app.logger.debug("<process_payment_action")
        action = request.get("action", None)
        statement_id = request.get("statementId", None)
        auth_account_id = request.get("accountId", None)
        try:
            match action:
                case EFTPaymentActions.APPLY_CREDITS.value:
                    EftService.apply_payment_action(short_name_id, auth_account_id, statement_id)
                case EFTPaymentActions.CANCEL.value:
                    EftService.cancel_payment_action(short_name_id, auth_account_id)
                case EFTPaymentActions.REVERSE.value:
                    EftService.reverse_payment_action(short_name_id, statement_id)
                case _:
                    raise BusinessException(Error.EFT_PAYMENT_ACTION_UNSUPPORTED)

            db.session.commit()
        except Exception:  # NOQA pylint:disable=broad-except
            db.session.rollback()
            raise
        current_app.logger.debug(">process_payment_action")

    @classmethod
    def patch_shortname(cls, short_name_id: int, request: Dict):
        """Patch EFT short name."""
        current_app.logger.debug("<patch_shortname")
        email = request.get("email", None)
        cas_supplier_number = request.get("casSupplierNumber", None)
        cas_supplier_site = request.get("casSupplierSite", None)
        short_name = EFTShortnameModel.find_by_id(short_name_id)

        if email is not None:
            short_name.email = email.strip()
        if cas_supplier_number is not None:
            short_name.cas_supplier_number = cas_supplier_number.strip()
        if cas_supplier_site is not None:
            short_name.cas_supplier_site = cas_supplier_site.strip()
        short_name.save()

        current_app.logger.debug(">patch_shortname")
        return cls.find_by_short_name_id(short_name_id)

    @classmethod
    def find_by_short_name_id(cls, short_name_id: int) -> EFTShortnames:
        """Find EFT short name by short name id."""
        current_app.logger.debug("<find_by_short_name_id")
        short_name_model: EFTShortnameModel = cls.get_search_query(EFTShortnamesSearch(id=short_name_id)).first()
        converter = Converter()
        result = converter.unstructure(EFTShortnameSchema.from_row(short_name_model)) if short_name_model else None

        current_app.logger.debug(">find_by_short_name_id")
        return result

    @classmethod
    def find_by_auth_account_id(cls, auth_account_id: str) -> List[EFTShortnames]:
        """Find EFT shortname by auth account id."""
        current_app.logger.debug("<find_by_auth_account_id")
        short_name_model: EFTShortnameModel = cls.get_search_query(
            EFTShortnamesSearch(account_id=auth_account_id)
        ).all()
        converter = Converter()
        result = converter.unstructure(EFTShortnameSchema.from_row(short_name_model))

        current_app.logger.debug(">find_by_auth_account_id")
        return result

    @classmethod
    def find_by_auth_account_id_state(cls, auth_account_id: str, state: List[str]) -> List[EFTShortnames]:
        """Find EFT shortname by auth account id that are linked."""
        current_app.logger.debug("<find_by_auth_account_id_state")
        short_name_models: EFTShortnameModel = cls.get_search_query(
            EFTShortnamesSearch(account_id=auth_account_id, allow_partial_account_id=False, state=state)
        ).all()

        result = unstructure_schema_items(EFTShortnameSchema, short_name_models)

        current_app.logger.debug(">find_by_auth_account_id_state")
        return result

    @classmethod
    def search(cls, search_criteria: EFTShortnamesSearch):
        """Search eft short name records."""
        current_app.logger.debug("<search")
        state_count = cls.get_search_count(search_criteria)
        search_query = cls.get_search_query(search_criteria)
        pagination = search_query.paginate(per_page=search_criteria.limit, page=search_criteria.page)

        short_name_list = unstructure_schema_items(EFTShortnameSchema, pagination.items)

        current_app.logger.debug(">search")
        return {
            "state_total": state_count,
            "page": search_criteria.page,
            "limit": search_criteria.limit,
            "items": short_name_list,
            "total": pagination.total,
        }

    @classmethod
    def get_search_count(cls, search_criteria: EFTShortnamesSearch):
        """Get total count of results based on short name state search criteria."""
        current_app.logger.debug("<get_search_count")

        query = cls.get_search_query(
            search_criteria=EFTShortnamesSearch(state=search_criteria.state),
            is_count=True,
        )
        count_query = query.group_by(EFTShortnameModel.id).with_entities(EFTShortnameModel.id)

        current_app.logger.debug(">get_search_count")
        return count_query.count()

    @classmethod
    def get_search_query(cls, search_criteria: EFTShortnamesSearch, is_count: bool = False):
        """Query for short names based on search criteria."""
        statement_summary_query = EFTStatements.get_statement_summary_query().subquery()

        # Case statement is to check for and remove the branch name from the name, so they can be filtered on separately
        # The branch name was added to facilitate a better short name search experience and the existing
        # name is preserved as it was with '-' concatenated with the branch name for reporting purposes
        links_subquery = (
            db.session.query(
                EFTShortnameLinksModel.eft_short_name_id,
                EFTShortnameLinksModel.status_code,
                EFTShortnameLinksModel.auth_account_id,
                case(
                    (
                        EFTShortnameLinksModel.auth_account_id.is_(None),
                        EFTShortnameStatus.UNLINKED.value,
                    ),
                    else_=EFTShortnameLinksModel.status_code,
                ).label("link_status_code"),
                CfsAccountModel.status.label("cfs_account_status"),
                PaymentAccountModel.name,
                PaymentAccountModel.branch_name,
            )
            .distinct(EFTShortnameLinksModel.auth_account_id)
            .outerjoin(
                PaymentAccountModel,
                PaymentAccountModel.auth_account_id == EFTShortnameLinksModel.auth_account_id,
            )
            .outerjoin(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id)
            .order_by(
                EFTShortnameLinksModel.auth_account_id,
                EFTShortnameLinksModel.updated_on.desc(),
            )
        )

        query = db.session.query(
            EFTShortnameModel.id,
            EFTShortnameModel.short_name,
            EFTShortnameModel.type,
            EFTShortnameModel.cas_supplier_number,
            EFTShortnameModel.cas_supplier_site,
            EFTShortnameModel.email,
            EFTShortnameModel.created_on,
        )

        # Join payment information if this is NOT the count query
        if not is_count:
            links_subquery = QueryUtils.add_payment_account_name_columns(links_subquery)

            links_subquery = links_subquery.add_columns(
                statement_summary_query.c.total_owing,
                statement_summary_query.c.latest_statement_id,
            ).outerjoin(
                statement_summary_query,
                statement_summary_query.c.payment_account_id == PaymentAccountModel.id,
            )

        links_subquery = links_subquery.filter(
            or_(
                CfsAccountModel.payment_method == PaymentMethod.EFT.value,
                CfsAccountModel.id.is_(None),
            )
        )
        links_subquery = links_subquery.filter(
            or_(
                PaymentAccountModel.payment_method == PaymentMethod.EFT.value,
                PaymentAccountModel.id.is_(None),
            )
        )

        links_subquery = links_subquery.subquery()
        query = query.outerjoin(links_subquery, links_subquery.c.eft_short_name_id == EFTShortnameModel.id)

        if not is_count:
            # Statement summary filters
            query = query.filter_conditionally(search_criteria.statement_id, links_subquery.c.latest_statement_id)
            if search_criteria.amount_owing == 0:
                query = query.filter(
                    or_(
                        links_subquery.c.total_owing == 0,
                        links_subquery.c.total_owing.is_(None),
                    )
                )
            else:
                query = query.filter_conditionally(search_criteria.amount_owing, links_subquery.c.total_owing)

            # Short name link filters
            query = query.filter_conditionally(
                search_criteria.account_id,
                links_subquery.c.auth_account_id,
                is_like=search_criteria.allow_partial_account_id,
            )
            # Payment account filters
            query = query.filter_conditionally(
                search_criteria.account_name,
                links_subquery.c.account_name,
                is_like=True,
            )
            query = query.filter_conditionally(
                search_criteria.account_branch,
                links_subquery.c.branch_name,
                is_like=True,
            )

            query = query.add_columns(
                links_subquery.c.eft_short_name_id,
                links_subquery.c.status_code,
                links_subquery.c.auth_account_id,
                links_subquery.c.link_status_code,
                links_subquery.c.cfs_account_status,
                links_subquery.c.account_name,
                links_subquery.c.account_branch,
                links_subquery.c.total_owing,
                links_subquery.c.latest_statement_id,
            )

        if search_criteria.account_id_list:
            query = query.filter(links_subquery.c.auth_account_id.in_(search_criteria.account_id_list))

        query = cls.get_link_state_filters(search_criteria, query, links_subquery)
        # Short name filters
        query = query.filter_conditionally(search_criteria.id, EFTShortnameModel.id)
        query = query.filter_conditionally(search_criteria.short_name_type, EFTShortnameModel.type)
        query = query.filter_conditionally(search_criteria.short_name, EFTShortnameModel.short_name, is_like=True)
        if not is_count:
            query = query.order_by(
                EFTShortnameModel.short_name.asc(),
                links_subquery.c.auth_account_id.asc(),
            )
        return query

    @classmethod
    def get_link_state_filters(cls, search_criteria, query, subquery=None):
        """Build filters for link states."""
        if not search_criteria.state:
            return query

        condition_status = EFTShortnameLinksModel.status_code if subquery is None else subquery.c.status_code
        if EFTShortnameStatus.UNLINKED.value in search_criteria.state:
            #  There can be multiple links to a short name, look for any links that don't have an UNLINKED status
            #  if they don't exist return the short name.
            condition_id = (
                EFTShortnameLinksModel.eft_short_name_id if subquery is None else subquery.c.eft_short_name_id
            )
            query = query.filter(
                ~exists()
                .where(condition_status != EFTShortnameStatus.UNLINKED.value)
                .where(condition_id == EFTShortnameModel.id)
                .correlate(EFTShortnameModel)
            )
        if EFTShortnameStatus.LINKED.value in search_criteria.state:
            query = query.filter(
                condition_status.in_([EFTShortnameStatus.PENDING.value, EFTShortnameStatus.LINKED.value])
            )
        return query
