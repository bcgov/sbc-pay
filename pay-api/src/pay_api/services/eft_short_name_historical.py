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
"""Service to manage EFT Short names historical data."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, case, exists, false, func, select
from sqlalchemy.orm import aliased

from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import EFTShortnameHistorySchema
from pay_api.models import EFTShortnamesHistorical as EFTShortnamesHistoricalModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.utils.enums import EFTHistoricalTypes
from pay_api.utils.user_context import user_context
from pay_api.utils.util import unstructure_schema_items


@dataclass
class EFTShortnameHistory:  # pylint: disable=too-many-instance-attributes
    """Used for creating EFT Short name historical data."""

    short_name_id: int
    amount: Decimal
    credit_balance: Decimal
    payment_account_id: Optional[int] = None
    related_group_link_id: Optional[int] = None
    statement_number: Optional[int] = None
    hidden: Optional[bool] = False
    is_processing: Optional[bool] = False
    invoice_id: Optional[int] = None
    eft_refund_id: Optional[int] = None
    transaction_date: Optional[datetime] = None


@dataclass
class EFTShortnameHistorySearch:
    """Used for searching EFT Short name historical records."""

    page: Optional[int] = 1
    limit: Optional[int] = 10


class EFTShortnameHistorical:
    """Service to manage EFT Short name historical data."""

    @staticmethod
    def create_funds_received(
        history: EFTShortnameHistory,
    ) -> EFTShortnamesHistoricalModel:
        """Create EFT Short name funds received historical record."""
        return EFTShortnamesHistoricalModel(
            amount=history.amount,
            created_by="SYSTEM",
            credit_balance=history.credit_balance,
            hidden=history.hidden,
            is_processing=history.is_processing,
            short_name_id=history.short_name_id,
            transaction_date=(
                history.transaction_date if history.transaction_date else EFTShortnameHistorical.transaction_date_now()
            ),
            transaction_type=EFTHistoricalTypes.FUNDS_RECEIVED.value,
        )

    @staticmethod
    @user_context
    def create_statement_paid(history: EFTShortnameHistory, **kwargs) -> EFTShortnamesHistoricalModel:
        """Create EFT Short name statement paid historical record."""
        return EFTShortnamesHistoricalModel(
            amount=history.amount,
            created_by=kwargs["user"].user_name,
            credit_balance=history.credit_balance,
            hidden=history.hidden,
            is_processing=history.is_processing,
            payment_account_id=history.payment_account_id,
            related_group_link_id=history.related_group_link_id,
            short_name_id=history.short_name_id,
            statement_number=history.statement_number,
            transaction_date=EFTShortnameHistorical.transaction_date_now(),
            transaction_type=EFTHistoricalTypes.STATEMENT_PAID.value,
        )

    @staticmethod
    @user_context
    def create_statement_reverse(history: EFTShortnameHistory, **kwargs) -> EFTShortnamesHistoricalModel:
        """Create EFT Short name statement reverse historical record."""
        return EFTShortnamesHistoricalModel(
            amount=history.amount,
            created_by=kwargs["user"].user_name,
            credit_balance=history.credit_balance,
            hidden=history.hidden,
            is_processing=history.is_processing,
            payment_account_id=history.payment_account_id,
            related_group_link_id=history.related_group_link_id,
            short_name_id=history.short_name_id,
            statement_number=history.statement_number,
            transaction_date=EFTShortnameHistorical.transaction_date_now(),
            transaction_type=EFTHistoricalTypes.STATEMENT_REVERSE.value,
        )

    @staticmethod
    @user_context
    def create_invoice_refund(history: EFTShortnameHistory, **kwargs) -> EFTShortnamesHistoricalModel:
        """Create EFT Short name invoice refund historical record."""
        return EFTShortnamesHistoricalModel(
            amount=history.amount,
            created_by=kwargs["user"].user_name,
            credit_balance=history.credit_balance,
            hidden=history.hidden,
            is_processing=history.is_processing,
            payment_account_id=history.payment_account_id,
            related_group_link_id=history.related_group_link_id,
            short_name_id=history.short_name_id,
            statement_number=history.statement_number,
            invoice_id=history.invoice_id,
            transaction_date=EFTShortnameHistorical.transaction_date_now(),
            transaction_type=EFTHistoricalTypes.INVOICE_REFUND.value,
        )

    @staticmethod
    @user_context
    def create_shortname_refund(history: EFTShortnameHistory, **kwargs) -> EFTShortnamesHistoricalModel:
        """Create EFT Short name refund historical record."""
        return EFTShortnamesHistoricalModel(
            amount=history.amount,
            created_by=kwargs["user"].user_name,
            credit_balance=history.credit_balance,
            hidden=history.hidden,
            is_processing=history.is_processing,
            short_name_id=history.short_name_id,
            eft_refund_id=history.eft_refund_id,
            transaction_date=EFTShortnameHistorical.transaction_date_now(),
            transaction_type=EFTHistoricalTypes.SN_REFUND_PENDING_APPROVAL.value,
        )

    @staticmethod
    def transaction_date_now() -> datetime:
        """Construct transaction datetime using the utc timezone."""
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def _get_account_name():
        """Return case statement for deriving payment account name."""
        return case(
            (
                PaymentAccountModel.name.like("%-" + PaymentAccountModel.branch_name),
                func.replace(PaymentAccountModel.name, "-" + PaymentAccountModel.branch_name, ""),
            ),
            else_=PaymentAccountModel.name,
        ).label("account_name")

    @classmethod
    def search(
        cls,
        short_name_id: int,
        search_criteria: EFTShortnameHistorySearch = EFTShortnameHistorySearch(),
    ):
        """Return EFT Short name history by search criteria."""
        history_model = aliased(EFTShortnamesHistoricalModel)
        latest_history_model = aliased(EFTShortnamesHistoricalModel)

        latest_history_subquery = (
            select(
                latest_history_model.statement_number,
                latest_history_model.transaction_type,
                latest_history_model.is_processing,
            )
            .where(
                latest_history_model.short_name_id == history_model.short_name_id,
                latest_history_model.statement_number == history_model.statement_number,
                latest_history_model.transaction_type != EFTHistoricalTypes.INVOICE_REFUND.value,
            )
            .order_by(
                latest_history_model.statement_number,
                latest_history_model.transaction_date.desc(),
                latest_history_model.id.desc(),
            )
            .limit(1)
            .correlate(history_model)
        ).subquery("latest_statement_history")

        # Reversible if:
        # - most recent state of the statement has been paid and not processing
        # - within 60 days of that transaction date
        # - is STATEMENT_PAID transaction type
        reversible_statement_subquery = exists(
            select(1)
            .select_from(latest_history_subquery)
            .where(
                and_(
                    latest_history_subquery.c.transaction_type == EFTHistoricalTypes.STATEMENT_PAID.value,
                    latest_history_subquery.c.is_processing.is_(False),
                )
            )
        )

        is_reversible_statement = case(
            (
                and_(
                    history_model.transaction_type == EFTHistoricalTypes.STATEMENT_PAID.value,
                    history_model.transaction_date >= cls.transaction_date_now() - timedelta(days=60),
                ),
                reversible_statement_subquery,
            ),
            else_=False,
        )

        query = (
            db.session.query(
                history_model.id,
                history_model.short_name_id,
                history_model.amount,
                history_model.credit_balance,
                history_model.invoice_id,
                history_model.eft_refund_id,
                history_model.statement_number,
                history_model.transaction_date,
                history_model.transaction_type,
                history_model.is_processing,
                PaymentAccountModel.auth_account_id,
                cls._get_account_name(),
                PaymentAccountModel.branch_name.label("account_branch"),
                is_reversible_statement.label("is_reversible"),
                EFTRefundModel.refund_method,
                EFTRefundModel.cheque_status,
            )
            .outerjoin(
                PaymentAccountModel,
                PaymentAccountModel.id == history_model.payment_account_id,
            )
            .outerjoin(EFTRefundModel, EFTRefundModel.id == history_model.eft_refund_id)
            .filter(history_model.short_name_id == short_name_id)
            .filter(history_model.hidden == false())
        )

        query = query.order_by(history_model.transaction_date.desc(), history_model.id.desc())

        pagination = query.paginate(per_page=search_criteria.limit, page=search_criteria.page)
        history_list = unstructure_schema_items(EFTShortnameHistorySchema, pagination.items)

        return {
            "page": search_criteria.page,
            "limit": search_criteria.limit,
            "items": history_list,
            "total": pagination.total,
        }
