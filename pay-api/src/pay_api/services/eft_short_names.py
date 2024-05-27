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
from datetime import date, datetime
from operator import and_
from typing import List, Optional

from _decimal import Decimal
from flask import current_app
from sqlalchemy import case, func, or_
from sqlalchemy.sql.expression import exists

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnameLinkSchema
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTShortnameSchema
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import db
from pay_api.utils.converter import Converter
from pay_api.utils.enums import EFTCreditInvoiceStatus, EFTShortnameStatus, InvoiceStatus, PaymentMethod
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context
from pay_api.utils.util import unstructure_schema_items


@dataclass
class EFTShortnamesSearch:  # pylint: disable=too-many-instance-attributes
    """Used for searching EFT short name records."""

    id: Optional[int] = None
    account_id: Optional[str] = None
    allow_partial_account_id: Optional[bool] = True
    account_name: Optional[str] = None
    account_branch: Optional[str] = None
    amount_owing: Optional[Decimal] = None
    deposit_start_date: Optional[date] = None
    deposit_end_date: Optional[date] = None
    credit_remaining: Optional[Decimal] = None
    linked_accounts_count: Optional[int] = None
    short_name: Optional[str] = None
    statement_id: Optional[int] = None
    state: Optional[List[str]] = None
    page: Optional[int] = 1
    limit: Optional[int] = 10


class EFTShortnames:  # pylint: disable=too-many-instance-attributes
    """Service to manage EFT short name model operations."""

    @classmethod
    @user_context
    def create_shortname_link(cls, short_name_id: int, auth_account_id: str, **kwargs) -> EFTShortnameLinksModel:
        """Create EFT short name auth account link."""
        current_app.logger.debug('<create_shortname_link')

        if auth_account_id is None:
            raise BusinessException(Error.EFT_SHORT_NAME_ACCOUNT_ID_REQUIRED)

        short_name: EFTShortnameModel = cls.find_by_auth_account_id_state(auth_account_id,
                                                                          [EFTShortnameStatus.LINKED.value,
                                                                           EFTShortnameStatus.PENDING.value])

        # This BCROS account already has an active link to a short name
        if short_name:
            raise BusinessException(Error.EFT_SHORT_NAME_ALREADY_MAPPED)

        eft_short_name_link = EFTShortnameLinksModel(
            eft_short_name_id=short_name_id,
            auth_account_id=auth_account_id,
            status_code=EFTShortnameStatus.PENDING.value,
            updated_by=kwargs['user'].user_name,
            updated_by_name=kwargs['user'].name,
            updated_on=datetime.now()
        ).save()

        current_app.logger.debug('>create_shortname_link')
        return cls.find_link_by_id(eft_short_name_link.id)

    @classmethod
    def delete_shortname_link(cls, short_name_link_id: int):
        """Delete EFT short name auth account link."""
        current_app.logger.debug('<delete_shortname_link')
        short_name_link: EFTShortnameLinksModel = EFTShortnameLinksModel.find_by_id(short_name_link_id)

        if short_name_link.status_code != EFTShortnameStatus.PENDING.value:
            raise BusinessException(Error.EFT_SHORT_NAME_LINK_INVALID_STATUS)

        short_name_link.delete()
        current_app.logger.debug('>delete_shortname_link')

    @classmethod
    def get_shortname_links(cls, short_name_id: int) -> List[EFTShortnameLinksModel]:
        """Get EFT short name account links."""
        current_app.logger.debug('<get_shortname_links')
        statement_summary_query = cls.get_statement_summary_query().subquery()
        invoice_count_query = cls.get_pending_payment_count()

        query = db.session.query(EFTShortnameLinksModel.id.label('id'),
                                 EFTShortnameLinksModel.eft_short_name_id,
                                 EFTShortnameLinksModel.status_code,
                                 EFTShortnameLinksModel.auth_account_id,
                                 EFTShortnameLinksModel.updated_by,
                                 EFTShortnameLinksModel.updated_by_name,
                                 EFTShortnameLinksModel.updated_on,
                                 invoice_count_query.label('invoice_count')) \
            .join(
                PaymentAccountModel,
                PaymentAccountModel.auth_account_id == EFTShortnameLinksModel.auth_account_id)

        query = cls.add_payment_account_name_columns(query)
        query = query.add_columns(
            statement_summary_query.c.total_owing,
            statement_summary_query.c.latest_statement_id
        ).outerjoin(
            statement_summary_query,
            statement_summary_query.c.payment_account_id == PaymentAccountModel.id
        ).filter(EFTShortnameLinksModel.eft_short_name_id == short_name_id) \
         .filter(EFTShortnameLinksModel.status_code.in_([EFTShortnameStatus.LINKED.value,
                                                         EFTShortnameStatus.PENDING.value]))

        query = query.order_by(EFTShortnameLinksModel.created_on.asc())

        link_models = query.all()
        link_list = unstructure_schema_items(EFTShortnameLinkSchema, link_models)

        current_app.logger.debug('>get_shortname_links')
        return {
            'items': link_list
        }

    @staticmethod
    def process_owing_invoices(short_name_id: int) -> EFTShortnames:
        """Process outstanding invoices when an EFT short name is mapped to an auth account id using credits."""
        current_app.logger.debug('<process_owing_invoices')
        short_name_model: EFTShortnameModel = EFTShortnameModel.find_by_id(short_name_id)
        auth_account_id = short_name_model.auth_account_id

        # Find invoices to be paid
        invoices: List[InvoiceModel] = EFTShortnames.get_invoices_owing(auth_account_id)
        pay_service = PaymentSystemFactory.create_from_payment_method(PaymentMethod.EFT.value)

        for invoice in invoices:
            pay_service.apply_credit(invoice)

        current_app.logger.debug('>process_owing_invoices')

    @staticmethod
    def get_invoices_owing(auth_account_id: str) -> [InvoiceModel]:
        """Return invoices that have not been fully paid."""
        unpaid_status = (InvoiceStatus.PARTIAL.value,
                         InvoiceStatus.CREATED.value, InvoiceStatus.OVERDUE.value)
        query = db.session.query(InvoiceModel) \
            .join(PaymentAccountModel, and_(PaymentAccountModel.id == InvoiceModel.payment_account_id,
                                            PaymentAccountModel.auth_account_id == auth_account_id)) \
            .filter(InvoiceModel.invoice_status_code.in_(unpaid_status)) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .order_by(InvoiceModel.created_on.asc())

        return query.all()

    @classmethod
    def find_by_short_name_id(cls, short_name_id: int) -> EFTShortnames:
        """Find EFT short name by short name id."""
        current_app.logger.debug('<find_by_short_name_id')
        short_name_model: EFTShortnameModel = cls.get_search_query(EFTShortnamesSearch(id=short_name_id)).first()
        converter = Converter()
        result = converter.unstructure(EFTShortnameSchema.from_row(short_name_model))

        current_app.logger.debug('>find_by_short_name_id')
        return result

    @classmethod
    def find_by_auth_account_id(cls, auth_account_id: str) -> List[EFTShortnames]:
        """Find EFT shortname by auth account id."""
        current_app.logger.debug('<find_by_auth_account_id')
        short_name_model: EFTShortnameModel = (cls.get_search_query(EFTShortnamesSearch(account_id=auth_account_id))
                                               .all())
        converter = Converter()
        result = converter.unstructure(EFTShortnameSchema.from_row(short_name_model))

        current_app.logger.debug('>find_by_auth_account_id')
        return result

    @classmethod
    def find_by_auth_account_id_state(cls, auth_account_id: str, state: List[str]) -> List[EFTShortnames]:
        """Find EFT shortname by auth account id that are linked."""
        current_app.logger.debug('<find_by_auth_account_id_state')
        short_name_models: EFTShortnameModel = cls.get_search_query(
            EFTShortnamesSearch(account_id=auth_account_id,
                                allow_partial_account_id=False,
                                state=state
                                )).all()

        result = unstructure_schema_items(EFTShortnameSchema, short_name_models)

        current_app.logger.debug('>find_by_auth_account_id_state')
        return result

    @classmethod
    def find_link_by_id(cls, link_id: int) -> List[EFTShortnames]:
        """Find EFT shortname link by id."""
        current_app.logger.debug('<find_link_by_id')
        link_model: EFTShortnameLinksModel = EFTShortnameLinksModel.find_by_id(link_id)
        converter = Converter()
        result = converter.unstructure(EFTShortnameLinkSchema.from_row(link_model))

        current_app.logger.debug('>find_link_by_id')
        return result

    @classmethod
    def search(cls, search_criteria: EFTShortnamesSearch):
        """Search eft short name records."""
        current_app.logger.debug('<search')
        state_count = cls.get_search_count(search_criteria)
        search_query = cls.get_search_query(search_criteria)
        pagination = search_query.paginate(per_page=search_criteria.limit,
                                           page=search_criteria.page)

        short_name_list = unstructure_schema_items(EFTShortnameSchema, pagination.items)

        current_app.logger.debug('>search')
        return {
            'state_total': state_count,
            'page': search_criteria.page,
            'limit': search_criteria.limit,
            'items': short_name_list,
            'total': pagination.total
        }

    @staticmethod
    def get_statement_summary_query():
        """Query for latest statement id and total amount owing of invoices in statements."""
        return db.session.query(
            StatementModel.payment_account_id,
            func.max(StatementModel.id).label('latest_statement_id'),
            func.coalesce(func.sum(InvoiceModel.total - InvoiceModel.paid), 0).label('total_owing')
        ).outerjoin(
            StatementInvoicesModel,
            StatementInvoicesModel.statement_id == StatementModel.id
        ).outerjoin(
            InvoiceModel,
            InvoiceModel.id == StatementInvoicesModel.invoice_id
        ).group_by(StatementModel.payment_account_id)

    @classmethod
    def get_search_count(cls, search_criteria: EFTShortnamesSearch):
        """Get total count of results based on short name state search criteria."""
        current_app.logger.debug('<get_search_count')

        query = cls.get_search_query(search_criteria=EFTShortnamesSearch(state=search_criteria.state), is_count=True)
        count_query = query.group_by(EFTShortnameModel.id).with_entities(EFTShortnameModel.id)

        current_app.logger.debug('>get_search_count')
        return count_query.count()

    @staticmethod
    def add_payment_account_name_columns(query):
        """Add payment account name and branch to query select columns."""
        return query.add_columns(case(
            (PaymentAccountModel.name.like('%-' + PaymentAccountModel.branch_name),
             func.replace(PaymentAccountModel.name, '-' + PaymentAccountModel.branch_name, '')
             ), else_=PaymentAccountModel.name).label('account_name'),
            PaymentAccountModel.branch_name.label('account_branch'))

    @staticmethod
    def get_pending_payment_count():
        """Get count of pending EFT Credit Invoice Links."""
        return (db.session.query(db.func.count(InvoiceModel.id).label('invoice_count'))
                .join(EFTCreditInvoiceLinkModel, EFTCreditInvoiceLinkModel.invoice_id == InvoiceModel.id)
                .filter(InvoiceModel.payment_account_id == PaymentAccountModel.id)
                .filter(EFTCreditInvoiceLinkModel.status_code.in_([EFTCreditInvoiceStatus.PENDING.value]))
                .correlate(PaymentAccountModel)
                .as_scalar())

    @classmethod
    def get_search_query(cls, search_criteria: EFTShortnamesSearch, is_count: bool = False):
        """Query for short names based on search criteria."""
        statement_summary_query = cls.get_statement_summary_query().subquery()

        # Case statement is to check for and remove the branch name from the name, so they can be filtered on separately
        # The branch name was added to facilitate a better short name search experience and the existing
        # name is preserved as it was with '-' concatenated with the branch name for reporting purposes
        query = (db.session.query(EFTShortnameModel.id,
                                  EFTShortnameModel.short_name,
                                  EFTShortnameModel.created_on,
                                  EFTShortnameLinksModel.status_code,
                                  EFTShortnameLinksModel.auth_account_id,
                                  case(
                                      (EFTShortnameLinksModel.auth_account_id.is_(None),
                                       EFTShortnameStatus.UNLINKED.value
                                       ),
                                      else_=EFTShortnameLinksModel.status_code
                                  ).label('status_code'),
                                  CfsAccountModel.status.label('cfs_account_status'))
                 .outerjoin(EFTShortnameLinksModel, EFTShortnameLinksModel.eft_short_name_id == EFTShortnameModel.id)
                 .outerjoin(PaymentAccountModel,
                            PaymentAccountModel.auth_account_id == EFTShortnameLinksModel.auth_account_id)
                 .outerjoin(CfsAccountModel,
                            CfsAccountModel.account_id == PaymentAccountModel.id))

        # Join payment information if this is NOT the count query
        if not is_count:
            query = cls.add_payment_account_name_columns(query)
            query = (query.add_columns(
                statement_summary_query.c.total_owing,
                statement_summary_query.c.latest_statement_id
            ).outerjoin(
                statement_summary_query,
                statement_summary_query.c.payment_account_id == PaymentAccountModel.id
            ))

            # Short name link filters
            query = query.filter_conditionally(search_criteria.id, EFTShortnameModel.id)
            query = query.filter_conditionally(search_criteria.account_id,
                                               EFTShortnameLinksModel.auth_account_id,
                                               is_like=True)
            # Payment account filters
            query = query.filter_conditionally(search_criteria.account_name, PaymentAccountModel.name, is_like=True)
            query = query.filter_conditionally(search_criteria.account_branch, PaymentAccountModel.branch_name,
                                               is_like=True)

            # Statement summary filters
            query = query.filter_conditionally(search_criteria.statement_id,
                                               statement_summary_query.c.latest_statement_id)
            if search_criteria.amount_owing == 0:
                query = query.filter(or_(statement_summary_query.c.total_owing == 0,
                                         statement_summary_query.c.total_owing.is_(None)))
            else:
                query = query.filter_conditionally(search_criteria.amount_owing, statement_summary_query.c.total_owing)

        query = cls.get_link_state_filters(search_criteria, query)
        query = query.filter(
            or_(PaymentAccountModel.payment_method == PaymentMethod.EFT.value, PaymentAccountModel.id.is_(None))
        )

        # Short name filters
        query = query.filter_conditionally(search_criteria.id, EFTShortnameModel.id)
        query = query.filter_conditionally(search_criteria.short_name, EFTShortnameModel.short_name, is_like=True)
        if not is_count:
            query = query.order_by(EFTShortnameModel.short_name.asc(), EFTShortnameLinksModel.auth_account_id.asc())
        return query

    @classmethod
    def get_link_state_filters(cls, search_criteria, query):
        """Build filters for link states."""
        if search_criteria.state:
            if EFTShortnameStatus.UNLINKED.value in search_criteria.state:
                #  There can be multiple links to a short name, look for any links that don't have an UNLINKED status
                #  if they don't exist return the short name.
                query = query.filter(
                    ~exists()
                    .where(EFTShortnameLinksModel.status_code != EFTShortnameStatus.UNLINKED.value)
                    .where(EFTShortnameLinksModel.eft_short_name_id == EFTShortnameModel.id)
                    .correlate(EFTShortnameModel)
                )
            if EFTShortnameStatus.LINKED.value in search_criteria.state:
                query = query.filter(
                    EFTShortnameLinksModel.status_code.in_([EFTShortnameStatus.PENDING.value,
                                                            EFTShortnameStatus.LINKED.value])
                )
        return query
