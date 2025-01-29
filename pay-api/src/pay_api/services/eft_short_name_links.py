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
"""Service to support EFT short name link operations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnameLinkSchema
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.utils.converter import Converter
from pay_api.utils.enums import EFTShortnameStatus
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context
from pay_api.utils.util import unstructure_schema_items

from ..utils.query_util import QueryUtils
from .eft_service import EftService
from .eft_statements import EFTStatements


class EFTShortnameLinks:
    """Service to support EFT short name links."""

    @classmethod
    def get_shortname_links(cls, short_name_id: int) -> dict:
        """Get EFT short name account links."""
        current_app.logger.debug("<get_shortname_links")
        statement_summary_query = EFTStatements.get_statement_summary_query().subquery()
        invoice_count_query = EftService.get_pending_payment_count()
        statements_owing = EFTStatements.get_statements_owing_as_array().subquery()

        query = db.session.query(
            EFTShortnameLinksModel.id.label("id"),
            EFTShortnameLinksModel.eft_short_name_id,
            EFTShortnameLinksModel.status_code,
            EFTShortnameLinksModel.auth_account_id,
            EFTShortnameLinksModel.updated_by,
            EFTShortnameLinksModel.updated_by_name,
            EFTShortnameLinksModel.updated_on,
            invoice_count_query.label("invoice_count"),
        ).join(
            PaymentAccountModel,
            PaymentAccountModel.auth_account_id == EFTShortnameLinksModel.auth_account_id,
        )

        query = QueryUtils.add_payment_account_name_columns(query)
        query = (
            query.add_columns(
                statement_summary_query.c.total_owing,
                statement_summary_query.c.latest_statement_id,
                statements_owing.c.statements,
            )
            .outerjoin(
                statement_summary_query,
                statement_summary_query.c.payment_account_id == PaymentAccountModel.id,
            )
            .outerjoin(
                statements_owing,
                statements_owing.c.id == PaymentAccountModel.id,
            )
            .filter(EFTShortnameLinksModel.eft_short_name_id == short_name_id)
            .filter(
                EFTShortnameLinksModel.status_code.in_(
                    [EFTShortnameStatus.LINKED.value, EFTShortnameStatus.PENDING.value]
                )
            )
        )

        query = query.order_by(EFTShortnameLinksModel.created_on.asc())
        link_models = query.all()
        link_list = unstructure_schema_items(EFTShortnameLinkSchema, link_models)
        current_app.logger.debug(">get_shortname_links")
        return {"items": link_list}

    @classmethod
    def patch_shortname_link(cls, link_id: int, request: Dict):
        """Patch EFT short name link."""
        current_app.logger.debug("<patch_shortname_link")
        valid_statuses = [EFTShortnameStatus.INACTIVE.value]
        status_code = request.get("statusCode", None)

        if status_code is None or status_code not in valid_statuses:
            raise BusinessException(Error.EFT_SHORT_NAME_LINK_INVALID_STATUS)

        shortname_link = EFTShortnameLinksModel.find_by_id(link_id)
        shortname_link.status_code = status_code
        shortname_link.save()

        current_app.logger.debug(">patch_shortname_link")
        return cls.find_link_by_id(link_id)

    @classmethod
    @user_context
    def create_shortname_link(cls, short_name_id: int, auth_account_id: str, **kwargs) -> EFTShortnameLinksModel:
        """Create EFT short name auth account link."""
        current_app.logger.debug("<create_shortname_link")

        if auth_account_id is None:
            raise BusinessException(Error.EFT_SHORT_NAME_ACCOUNT_ID_REQUIRED)

        link_count = EFTShortnameLinksModel.get_short_name_links_count(auth_account_id)

        # This BCROS account already has an active link to a short name
        if link_count > 0:
            raise BusinessException(Error.EFT_SHORT_NAME_ALREADY_MAPPED)

        # Re-activate link if it previously existed
        eft_short_name_link = EFTShortnameLinksModel.find_inactive_link(short_name_id, auth_account_id)
        if eft_short_name_link is None:
            eft_short_name_link = EFTShortnameLinksModel(
                eft_short_name_id=short_name_id,
                auth_account_id=auth_account_id,
            )

        eft_short_name_link.status_code = EFTShortnameStatus.PENDING.value
        eft_short_name_link.updated_by = kwargs["user"].user_name
        eft_short_name_link.updated_by_name = kwargs["user"].name
        eft_short_name_link.updated_on = datetime.now(tz=timezone.utc)

        db.session.add(eft_short_name_link)
        db.session.flush()

        EftService.process_owing_statements(
            short_name_id=short_name_id,
            auth_account_id=auth_account_id,
            is_new_link=True,
        )

        eft_short_name_link.save()
        current_app.logger.debug(">create_shortname_link")
        return cls.find_link_by_id(eft_short_name_link.id)

    @classmethod
    def delete_shortname_link(cls, short_name_link_id: int):
        """Delete EFT short name auth account link."""
        current_app.logger.debug("<delete_shortname_link")
        short_name_link: EFTShortnameLinksModel = EFTShortnameLinksModel.find_by_id(short_name_link_id)

        if short_name_link.status_code != EFTShortnameStatus.PENDING.value:
            raise BusinessException(Error.EFT_SHORT_NAME_LINK_INVALID_STATUS)

        short_name_link.delete()
        current_app.logger.debug(">delete_shortname_link")

    @staticmethod
    def find_link_by_id(link_id: int):
        """Find EFT shortname link by id."""
        current_app.logger.debug("<find_link_by_id")
        link_model: EFTShortnameLinksModel = EFTShortnameLinksModel.find_by_id(link_id)
        converter = Converter()
        result = converter.unstructure(EFTShortnameLinkSchema.from_row(link_model))

        current_app.logger.debug(">find_link_by_id")
        return result
